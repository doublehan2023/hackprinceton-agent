from fastapi import APIRouter

from backend.repository import list_versions
from backend.schemas import VersionSummary

router = APIRouter()


@router.get("/versions/{negotiation_id}", response_model=list[VersionSummary])
def get_versions(negotiation_id: str) -> list[VersionSummary]:
    return list_versions(negotiation_id)
