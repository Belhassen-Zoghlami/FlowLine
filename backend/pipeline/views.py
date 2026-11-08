from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .ingestion import IngestionError,handle_delivery

@csrf_exempt
def github_webhook(request):
    if request.method != "POST":
        return JsonResponse({"detail":"Method not allowed"}, status=405)
    try:
        code,result= handle_delivery(
            request.headers.get("X-GitHub-Event",""),
            request.body,
            request.headers.get("X-Hub-Signature-256",""),
        )
    except IngestionError as excep:
        return JsonResponse(
            {"detail":excep.detail},
            status=excep.status
            )
    return JsonResponse(result,status=code)
# Create your views here.
