import json
import requests
from django.conf import settings
from pipeline import github
from .models import Repository, Run
from .pipeline import extract_entries, process_run
from .security import verify_webhook_signature

FAILURES = {"failure", "timed_out"}


class IngestionError(Exception):
    def __init__(self, detail, status=400):
        super().__init__(detail)
        self.detail = detail
        self.status = status


def fetch_run_logs(full_name, run_id, token=""):
    response = github.get(f"/repos/{full_name}/actions/runs/{run_id}/logs", token)
    if response.status_code in (404, 410, 204):
        return None
    response.raise_for_status()
    return response.content


def handle_delivery(event, body, signature_header):
    try:
        payload = json.loads(body)
    except (TypeError, ValueError) as exc:
        raise IngestionError("Malformed JSON body.") from exc

    if not isinstance(payload, dict):
        raise IngestionError("Malformed JSON body.")

    full_name = (payload.get("repository") or {}).get("full_name", "")
    repository = Repository.objects.filter(github_name=full_name).first()
    if repository is None:
        raise IngestionError("Repository is not registered with FlowLine.", 404)

    secret = repository.webhook_secret or settings.GITHUB_WEBHOOK_SECRET
    if not verify_webhook_signature(secret, body, signature_header):
        raise IngestionError("Invalid webhook signature.", 401)

    if event == "ping":
        return 200, {"detail": "pong", "repository": repository.github_name}

    if event != "workflow_run":
        return 202, {
            "detail": f"event '{event}' ignored",
            "repository": repository.github_name,
        }

    data = payload.get("workflow_run") or {}
    run_id = data.get("id")
    if not run_id:
        raise IngestionError("workflow_run payload carries no run id.")

    conclusion = data.get("conclusion")
    if conclusion not in FAILURES:
        return 200, {
            "detail": f"conclusion '{conclusion}' ignored",
            "repository": repository.github_name,
            "run_id": run_id,
        }

    run, created = Run.objects.get_or_create(
        repository=repository,
        github_run_id=run_id,
        defaults={
            "run_number": data.get("run_number") or 0,
            "commit_sha": data.get("head_sha") or "",
            "branch": data.get("head_branch") or "",
            "status": conclusion or data.get("status") or "",
        },
    )

    if not created and conclusion and run.status != conclusion:
        run.status = conclusion
        run.save(update_fields=["status"])

    try:
        archive = fetch_run_logs(
            repository.github_name,
            run_id,
            repository.access_token,
        )
    except requests.RequestException as exc:
        raise IngestionError(
            "Could not retrieve the run logs from GitHub.", 502
        ) from exc

    entries = []
    problem = None
    if archive:
        entries = extract_entries(archive)
        _, problem = process_run(run, entries)

    return 200, {
        "detail": "failure recorded",
        "repository": repository.github_name,
        "run_id": run_id,
        "run_created": created,
        "status": run.status,
        "log_fetched": bool(archive),
        "log_bytes": len(archive or b""),
        "log_entries": len(entries),
        "signature": run.signature,
        "failed_step": run.failed_step,
        "is_parsed": run.is_parsed,
        "problem_id": problem.pk if problem else None,
        "num_occurrences": problem.num_occurrences if problem else None,
    }
