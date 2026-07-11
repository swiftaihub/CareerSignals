from __future__ import annotations

from io import BytesIO

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
import pandas as pd

from apps.api.dependencies.authorization import CurrentUser, require_non_demo_user
from apps.api.dependencies.repositories import get_repository
from packages.careersignal_core.repositories.jobs import JobFilters, JobRepository

router = APIRouter(prefix="/api/exports", tags=["exports"])


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
    filename = f"careersignals-{str(current_user.user_uuid)[:8]}.xlsx"
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "private, no-store",
        },
    )
