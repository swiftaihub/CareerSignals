from __future__ import annotations

from fastapi import APIRouter

from apps.api.dependencies.models import APIError

router = APIRouter(prefix="/api", tags=["deprecated"])


def _gone() -> None:
    raise APIError(
        410,
        "This operational endpoint was removed. Submit a personal run through /api/pipeline-runs.",
        "OPERATIONAL_ENDPOINT_REMOVED",
    )


@router.post("/pipeline/run", include_in_schema=False)
def old_pipeline_run() -> None:
    _gone()


@router.post("/dbt/run", include_in_schema=False)
def old_dbt_run() -> None:
    _gone()


@router.post("/dbt/test", include_in_schema=False)
def old_dbt_test() -> None:
    _gone()


@router.post("/excel/export", include_in_schema=False)
def old_excel_export() -> None:
    _gone()


@router.get("/excel/download", include_in_schema=False)
def old_excel_download() -> None:
    _gone()
