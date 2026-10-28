"""Tests for CSV import security."""
import io

import pytest
from fastapi import UploadFile

from app.services.csv_service import parse_guest_csv


def _make_upload(content: str, content_type: str = "text/csv") -> UploadFile:
    return UploadFile(
        filename="guests.csv",
        file=io.BytesIO(content.encode("utf-8")),
        headers={"content-type": content_type},
    )


class TestCsvImport:
    @pytest.mark.asyncio
    async def test_valid_csv(self):
        csv_content = "name,email,rsvp_status\nRavi,ravi@example.com,confirmed\n"
        upload = _make_upload(csv_content)
        rows = await parse_guest_csv(upload)
        assert len(rows) == 1
        assert rows[0]["name"] == "Ravi"

    @pytest.mark.asyncio
    async def test_missing_name_column_rejected(self):
        from fastapi import HTTPException
        csv_content = "email,phone\ntest@example.com,123\n"
        upload = _make_upload(csv_content)
        with pytest.raises(HTTPException) as exc:
            await parse_guest_csv(upload)
        assert exc.value.status_code == 400

    @pytest.mark.asyncio
    async def test_formula_injection_neutralized(self):
        csv_content = "name,email\n=SUM(A1),evil@example.com\n"
        upload = _make_upload(csv_content)
        rows = await parse_guest_csv(upload)
        # Formula injection cells get a ' prefix
        assert rows[0]["name"].startswith("'")

    @pytest.mark.asyncio
    async def test_file_too_large_rejected(self, monkeypatch):
        from fastapi import HTTPException

        import app.config.settings as settings_module
        monkeypatch.setattr(settings_module.get_settings(), "UPLOAD_MAX_BYTES", 10)
        csv_content = "name\n" + "A" * 20
        upload = _make_upload(csv_content)
        with pytest.raises(HTTPException) as exc:
            await parse_guest_csv(upload)
        assert exc.value.status_code == 400

    @pytest.mark.asyncio
    async def test_binary_file_rejected(self):
        from fastapi import HTTPException
        binary_content = b"\x00\x01\x02\x03" * 100
        upload = UploadFile(
            filename="evil.csv",
            file=io.BytesIO(binary_content),
            headers={"content-type": "text/csv"},
        )
        with pytest.raises(HTTPException) as exc:
            await parse_guest_csv(upload)
        assert exc.value.status_code == 400

    @pytest.mark.asyncio
    async def test_null_byte_after_initial_content_rejected(self):
        from fastapi import HTTPException
        binary_content = b"name\nRavi\n" + b"A" * 600 + b"\x00"
        upload = UploadFile(
            filename="guests.csv",
            file=io.BytesIO(binary_content),
            headers={"content-type": "text/csv"},
        )
        with pytest.raises(HTTPException) as exc:
            await parse_guest_csv(upload)
        assert exc.value.status_code == 400

    @pytest.mark.asyncio
    async def test_rows_with_empty_name_skipped(self):
        csv_content = "name,email\nRavi,r@e.com\n,missing@name.com\n"
        upload = _make_upload(csv_content)
        rows = await parse_guest_csv(upload)
        assert len(rows) == 1
        assert rows[0]["name"] == "Ravi"
