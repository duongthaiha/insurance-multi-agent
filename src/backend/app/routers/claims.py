from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from ..services.sql_store import SQLStore

router = APIRouter(prefix="/api/claims", tags=["claims"])


class Claim(BaseModel):
    claim_id: str
    claimant_name: str
    incident_date: str
    summary: Optional[str] = None
    status: str = "pending"


@router.get("/{claim_id}")
async def get_claim(claim_id: str, sql: SQLStore = Depends()):
    return await sql.get_claim(claim_id)


@router.get("/{claim_id}/images")
async def list_images(claim_id: str, sql: SQLStore = Depends()):
    return await sql.list_images(claim_id)


@router.get("/{claim_id}/transcripts")
async def list_transcripts(claim_id: str, sql: SQLStore = Depends()):
    return await sql.list_transcripts(claim_id)
