from __future__ import annotations

from datetime import datetime
from io import BytesIO
import secrets
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
import pandas as pd

from apps.api.dependencies.authorization import CurrentUser, require_non_demo_user
from apps.api.dependencies.repositories import get_repository
from packages.careersignal_core.repositories.jobs import JobFilters, JobRepository
from packages.careersignal_core.settings import get_settings

router = APIRouter(prefix="/api/exports", tags=["exports"])


def build_export_filename(
    *,
    now: datetime | None = None,
    unique_suffix: str | None = None,
) -> str:
    """Return a public, collision-safe workbook name without tenant identifiers."""

    if now is None:
        timezone_name = get_settings().connector_refresh_timezone
        try:
            now = datetime.now(ZoneInfo(timezone_name))
        except ZoneInfoNotFoundError:
            now = datetime.now().astimezone()
    suffix = unique_suffix or secrets.token_hex(3)
    safe_suffix = "".join(character for character in suffix if character.isalnum())[:12]
    if not safe_suffix:
        safe_suffix = secrets.token_hex(3)
    return f"CareerSignals_Matches_{now.date().isoformat()}_{safe_suffix}.xlsx"


@router.post("/excel")
def export_excel(
    current_user: CurrentUser = Depends(require_non_demo_user),
    repository: JobRepository = Depends(get_repository),
) -> StreamingResponse:
    rows = repository.get_jobs(JobFilters(limit=5000, sort_by="match_score", sort_order="desc")).items
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        pd.DataFrame(rows).to_excel(writer, sheet_name="My Matches", index=False)
        pd.DataFrame(repository.get_category_summary()).to_excel(
            writer, sheet_name="Category Summary", index=False
        )
        pd.DataFrame(repository.get_skill_gap()).to_excel(writer, sheet_name="Skill Gap", index=False)
        pd.DataFrame(repository.get_company_priority()).to_excel(
            writer, sheet_name="Company Priority", index=False
        )
    output.seek(0)
    filename = build_export_filename()
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "private, no-store",
        },
    )
