import io
import zipfile

from .grouping import group_run
from .parsing import parse_entries
from .classification import classify_signature
from .models import FaultCategory

MAX_ENTRIES = 200
MAX_ENTRY_BYTES = 2_000_000
MAX_TOTAL_BYTES = 20_000_000


def extract_entries(archive):
    if not isinstance(archive, (bytes, bytearray)) or not archive:
        return []

    try:
        if not zipfile.is_zipfile(io.BytesIO(archive)):
            return []

        entries = []
        total = 0
        with zipfile.ZipFile(io.BytesIO(archive)) as zf:
            for info in zf.infolist():
                if info.is_dir() or info.file_size > MAX_ENTRY_BYTES:
                    continue
                if total + info.file_size > MAX_TOTAL_BYTES:
                    break

                data = zf.read(info)
                total += len(data)
                entries.append((info.filename, data.decode("utf-8", "replace")))

                if len(entries) >= MAX_ENTRIES:
                    break

        return entries
    except (OSError, RuntimeError, zipfile.BadZipFile):
        return []


def process_run(run, entries):
    parsed = parse_entries(entries)

    run.signature = parsed.signature
    run.failed_step = parsed.failed_step
    run.is_parsed = parsed.is_parsed
    run.save(update_fields=["signature", "failed_step", "is_parsed"])

    problem = group_run(run, parsed.signature)
    if problem is not None:
        category = classify_signature(parsed.signature)
        if category != FaultCategory.UNKNOWN and problem.category != category:
            problem.category = category
            problem.save(update_fields=["category"])
    return parsed, problem
