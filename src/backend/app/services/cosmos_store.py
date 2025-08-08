from typing import List, Dict, Optional
from pydantic import BaseModel
from enum import StrEnum
import datetime as dt
import uuid

try:
    from azure.cosmos import CosmosClient, PartitionKey, exceptions
except Exception:  # pragma: no cover
    CosmosClient = None  # type: ignore
    PartitionKey = None  # type: ignore
    exceptions = None  # type: ignore


class JobState(StrEnum):
    PENDING = "pending"
    AWAITING_USER_INPUT = "awaiting_user_input"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class JobRecord(BaseModel):
    id: str
    state: JobState
    session_id: str
    context: Dict
    updated_at: str


class ConversationStore:
    def __init__(self, cosmos_url: str, cosmos_key: str, database: str, container: str):
        self.url = cosmos_url
        self.key = cosmos_key
        self.database_name = database
        self.container_name = container
        self.client = CosmosClient(self.url, credential=self.key) if (self.url and self.key and CosmosClient) else None
        self._container = None

    def _get_container(self):
        if not self.client:
            return None
        if self._container is None:
            db = self.client.create_database_if_not_exists(id=self.database_name)
            self._container = db.create_container_if_not_exists(id=self.container_name, partition_key=PartitionKey(path="/session_id"))
        return self._container

    async def append_message(self, session_id: str, sender: str, text: str):
        ctn = self._get_container()
        item = {
            "id": str(uuid.uuid4()),
            "session_id": session_id,
            "type": "message",
            "sender": sender,
            "text": text,
            "ts": dt.datetime.utcnow().isoformat() + "Z",
        }
        if ctn:
            ctn.upsert_item(item)
        else:
            # fallback: no-op or in-memory stub could be added if desired
            pass

    async def get_messages(self, session_id: str) -> List[Dict]:
        ctn = self._get_container()
        if not ctn:
            return []
        query = "SELECT c.id, c.sender, c.text, c.ts FROM c WHERE c.session_id = @sid AND c.type = 'message' ORDER BY c.ts ASC"
        items = list(ctn.query_items(query=query, parameters=[{"name": "@sid", "value": session_id}], enable_cross_partition_query=True))
        return items

    async def create_job(self, session_id: str, context: Dict) -> JobRecord:
        ctn = self._get_container()
        rec = JobRecord(id=str(uuid.uuid4()), state=JobState.PENDING, session_id=session_id, context=context, updated_at=dt.datetime.utcnow().isoformat() + "Z")
        if ctn:
            ctn.upsert_item(rec.model_dump())
        return rec

    async def get_job(self, job_id: str) -> Optional[Dict]:
        ctn = self._get_container()
        if not ctn:
            return None
        try:
            query = "SELECT * FROM c WHERE c.id = @id"
            items = list(ctn.query_items(query=query, parameters=[{"name": "@id", "value": job_id}], enable_cross_partition_query=True))
            return items[0] if items else None
        except Exception:
            return None

    async def update_job_state(self, job_id: str, state: JobState, patch: Optional[Dict] = None):
        ctn = self._get_container()
        if not ctn:
            return
        items = list(ctn.query_items(query="SELECT * FROM c WHERE c.id = @id", parameters=[{"name": "@id", "value": job_id}], enable_cross_partition_query=True))
        if not items:
            return
        item = items[0]
        item["state"] = state
        item["updated_at"] = dt.datetime.utcnow().isoformat() + "Z"
        if patch:
            item.setdefault("context", {}).update(patch)
        ctn.upsert_item(item)
