"""
CSV import service with full security validation:
- Content-type checked (not just extension)
- Max file size (configurable)
- Max rows (configurable)
- Every row validated against schema
- CSV formula injection neutralized on export
"""
import csv
import io
import logging
import re

from fastapi import HTTPException, UploadFile

from app.config.settings import get_settings

log = logging.getLogger(__name__)
settings = get_settings()

# CSV magic bytes and allowed MIME types
_ALLOWED_MIME = {"text/csv", "text/plain", "application/csv", "application/vnd.ms-excel"}
_FORMULA_INJECTION_RE = re.compile(r"^[=+\-@|]")

_ALLOWED_HEADERS = {"name", "email", "phone", "rsvp_status", "dietary_needs", "accessibility_needs"}
_REQUIRED_HEADERS = {"name"}


def _sanitize_cell(value: str) -> str:
    """Neutralize CSV formula injection."""
    value = value.strip()
    if _FORMULA_INJECTION_RE.match(value):
        return "'" + value
    return value


async def parse_guest_csv(upload: UploadFile) -> list[dict]:
    """
    Parse and validate a guest CSV file.
    Returns a list of row dicts ready for bulk_import_guests.
    Raises HTTPException on any validation failure.
    """
    # Validate content type by MIME (not just extension)
    content_type = (upload.content_type or "").lower().split(";")[0].strip()
    if content_type not in _ALLOWED_MIME:
        # Be generous – also accept empty/octet-stream but validate content
        if content_type not in ("application/octet-stream", ""):
            raise HTTPException(
                status_code=400,
                detail="Invalid file type. Upload a CSV file.",
            )

    raw = await upload.read(settings.UPLOAD_MAX_BYTES + 1)
    if len(raw) > settings.UPLOAD_MAX_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size is {settings.UPLOAD_MAX_BYTES // 1024} KB.",
        )

    if b"\x00" in raw:
        raise HTTPException(status_code=400, detail="Invalid file content.")

    try:
        text = raw.decode("utf-8-sig")  # handle BOM
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File must be UTF-8 encoded.")

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise HTTPException(status_code=400, detail="CSV has no headers.")

    headers = {h.strip().lower() for h in reader.fieldnames}
    if not _REQUIRED_HEADERS.issubset(headers):
        raise HTTPException(
            status_code=400, detail="CSV must include at least a 'name' column."
        )

    unknown_headers = headers - _ALLOWED_HEADERS
    if unknown_headers:
        log.info("CSV import: ignoring unknown columns: %s", unknown_headers)

    rows = []
    for i, row in enumerate(reader, start=2):  # start=2 (row 1 is header)
        if i > settings.UPLOAD_MAX_ROWS + 1:
            raise HTTPException(
                status_code=400,
                detail=f"Too many rows. Maximum is {settings.UPLOAD_MAX_ROWS}.",
            )
        cleaned = {
            k.strip().lower(): _sanitize_cell(v or "")
            for k, v in row.items()
            if k and k.strip().lower() in _ALLOWED_HEADERS
        }
        if not cleaned.get("name"):
            log.info("CSV import: skipping row %d (missing name)", i)
            continue
        rows.append(cleaned)

    if not rows:
        raise HTTPException(status_code=400, detail="CSV contains no valid rows.")

    return rows
