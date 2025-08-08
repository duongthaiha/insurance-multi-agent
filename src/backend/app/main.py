from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import os
import uuid
from typing import List, Dict, Optional

from .services.webpubsub import WebPubSubHub
from .services.cosmos_store import ConversationStore, JobState, JobRecord
from .services.sql_store import SQLStore
from .services.blob_store import BlobStore
from .routers import __init__ as routers_init  # noqa: F401
from .routers.claims import router as claims_router

app = FastAPI(title="Insurance Multi-Agent Backend", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(claims_router)

# Dependency providers

def get_webpubsub() -> WebPubSubHub:
    return WebPubSubHub(
        connection_string=os.getenv("WEBPUBSUB_CONNECTION_STRING", ""),
        hub=os.getenv("WEBPUBSUB_HUB", "claims"),
    )


def get_conv_store() -> ConversationStore:
    return ConversationStore(
        cosmos_url=os.getenv("COSMOS_URL", ""),
        cosmos_key=os.getenv("COSMOS_KEY", ""),
        database=os.getenv("COSMOS_DB", "claimsdb"),
        container=os.getenv("COSMOS_CONTAINER", "conversations"),
    )


def get_sql_store() -> SQLStore:
    return SQLStore(
        server=os.getenv("SQL_SERVER", ""),
        database=os.getenv("SQL_DATABASE", "claimsdb"),
        user=os.getenv("SQL_USER"),
        password=os.getenv("SQL_PASSWORD"),
    )


def get_blob_store() -> BlobStore:
    return BlobStore(
        connection_string=os.getenv("BLOB_CONNECTION_STRING", ""),
        container=os.getenv("BLOB_CONTAINER", "claim-artifacts"),
    )


class ChatMessage(BaseModel):
    session_id: str
    sender: str
    text: str


class ResumeJobRequest(BaseModel):
    job_id: str
    user_input: str


@app.get("/api/webpubsub/token")
async def get_webpubsub_token(user_id: str | None = None, wps: WebPubSubHub = Depends(get_webpubsub)):
    token = await wps.get_client_access_token(user_id=user_id)
    return token


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, conv_store: ConversationStore = Depends(get_conv_store), wps: WebPubSubHub = Depends(get_webpubsub)):
    await websocket.accept()
    session_id = None
    try:
        while True:
            msg = await websocket.receive_json()
            if "session_id" not in msg:
                session_id = str(uuid.uuid4())
                await websocket.send_json({"type": "session", "session_id": session_id})
            else:
                session_id = msg.get("session_id")
            text = msg.get("text", "")
            sender = msg.get("sender", "user")
            # Save incoming message
            await conv_store.append_message(session_id, sender, text)
            # Simple echo + simulate backend agent routing
            reply = f"Thanks for your message. Our claim assistant is processing: {text[:200]}"
            await conv_store.append_message(session_id, "assistant", reply)
            await websocket.send_json({"type": "message", "sender": "assistant", "text": reply})
            # Broadcast via Azure Web PubSub for other clients
            await wps.send_to_all("chat.update", {"session_id": session_id, "sender": sender, "text": text})
            await wps.send_to_all("chat.update", {"session_id": session_id, "sender": "assistant", "text": reply})
    except WebSocketDisconnect:
        return


@app.post("/api/chat")
async def chat(msg: ChatMessage, conv_store: ConversationStore = Depends(get_conv_store), wps: WebPubSubHub = Depends(get_webpubsub)):
    await conv_store.append_message(msg.session_id, msg.sender, msg.text)
    reply = f"Received: {msg.text[:200]}"
    await conv_store.append_message(msg.session_id, "assistant", reply)
    # Broadcast both user and assistant to the hub
    await wps.send_to_all("chat.update", {"session_id": msg.session_id, "sender": msg.sender, "text": msg.text})
    await wps.send_to_all("chat.update", {"session_id": msg.session_id, "sender": "assistant", "text": reply})
    return {"reply": reply}


@app.post("/api/upload/image")
async def upload_image(
    claim_id: str,
    file: UploadFile = File(...),
    blob: BlobStore = Depends(get_blob_store),
    sql: SQLStore = Depends(get_sql_store),
):
    blob_url = await blob.upload_file(file)
    await sql.link_image(claim_id, blob_url)
    return {"status": "uploaded", "url": blob_url}


@app.post("/api/upload/transcript")
async def upload_transcript(
    claim_id: str,
    file: UploadFile = File(...),
    blob: BlobStore = Depends(get_blob_store),
    sql: SQLStore = Depends(get_sql_store),
):
    blob_url = await blob.upload_file(file)
    await sql.link_transcript(claim_id, blob_url)
    return {"status": "uploaded", "url": blob_url}


@app.post("/api/jobs/resume")
async def resume_job(req: ResumeJobRequest, conv_store: ConversationStore = Depends(get_conv_store)):
    job = await conv_store.get_job(req.job_id)
    if not job:
        return JSONResponse(status_code=404, content={"error": "job not found"})
    await conv_store.update_job_state(req.job_id, JobState.PROCESSING, {"user_input": req.user_input})
    # Simulate some processing and completion
    await conv_store.update_job_state(req.job_id, JobState.COMPLETED, {"result": "updated with user input"})
    return {"status": "resumed", "job_id": req.job_id}


@app.post("/api/workflow/start")
async def start_workflow(session_id: str, text: str, conv_store: ConversationStore = Depends(get_conv_store), wps: WebPubSubHub = Depends(get_webpubsub)):
    # Very simple demo: create a job and request user input
    job = await conv_store.create_job(session_id, {"initial_text": text})
    await conv_store.update_job_state(job.id, JobState.AWAITING_USER_INPUT, {"missing": "Please provide license plate number"})
    await wps.send_to_all("job.update", {"job_id": job.id, "state": JobState.AWAITING_USER_INPUT, "missing": "license_plate"})
    return {"job_id": job.id, "state": JobState.AWAITING_USER_INPUT}


@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str, conv_store: ConversationStore = Depends(get_conv_store)):
    job = await conv_store.get_job(job_id)
    if not job:
        return JSONResponse(status_code=404, content={"error": "job not found"})
    return job


@app.get("/api/conversations/{session_id}")
async def get_conversation(session_id: str, conv_store: ConversationStore = Depends(get_conv_store)):
    messages = await conv_store.get_messages(session_id)
    return {"session_id": session_id, "messages": messages}
