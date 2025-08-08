from typing import Dict
import asyncio
from .services.cosmos_store import ConversationStore, JobState


class ClaimWorkflow:
    def __init__(self, conv: ConversationStore):
        self.conv = conv

    async def start_claim_intake(self, session_id: str, initial_text: str) -> Dict:
        # Create a job that might pause for user input in the middle
        job = await self.conv.create_job(session_id, {"initial_text": initial_text})
        await self.conv.update_job_state(job.id, JobState.PROCESSING)
        # Simulate steps
        await asyncio.sleep(0.1)
        # Ask for missing data
        await self.conv.update_job_state(job.id, JobState.AWAITING_USER_INPUT, {"missing": "Please provide license plate number"})
        return {"job_id": job.id}
