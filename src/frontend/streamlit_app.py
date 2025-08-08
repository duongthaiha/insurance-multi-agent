import os
import json
import streamlit as st
import uuid
import time
import requests
import threading
import queue
from urllib.parse import urlparse, urlunparse
from websockets.sync.client import connect as ws_connect

# Streamlit page config MUST be first Streamlit command
st.set_page_config(page_title="Insurance Claim Assistant", page_icon="🚗", layout="wide")

"""
Config & endpoints
- Prefer BACKEND_URL env; derive WS URL from it to avoid mismatches.
- Allow optional WS_URL override via env if explicitly set.
"""

def _derive_ws_url(http_url: str) -> str:
    try:
        p = urlparse(http_url)
        scheme = "wss" if p.scheme == "https" else "ws"
        # Force path to /ws; keep netloc and query/fragment empty
        return urlunparse((scheme, p.netloc, "/ws", "", "", ""))
    except Exception:
        return "ws://localhost:8000/ws"

BACKEND_URL_ENV = os.getenv("BACKEND_URL", "http://localhost:8000")
WS_URL_ENV = os.getenv("WS_URL")

if "backend_url" not in st.session_state:
    st.session_state.backend_url = BACKEND_URL_ENV
if "ws_url" not in st.session_state:
    st.session_state.ws_url = WS_URL_ENV or _derive_ws_url(st.session_state.backend_url)

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "ws_connected" not in st.session_state:
    st.session_state.ws_connected = False
if "ws_in_q" not in st.session_state:
    st.session_state.ws_in_q = queue.Queue()
if "ws_out_q" not in st.session_state:
    st.session_state.ws_out_q = queue.Queue()
if "ws_thread" not in st.session_state:
    st.session_state.ws_thread = None

st.title("Motor Car Insurance Claims")

# WebSocket client thread
def _ws_loop(url: str, session_id: str, in_q: queue.Queue, out_q: queue.Queue):
    try:
        # Connect without subprotocol to avoid negotiation issues
        with ws_connect(url) as ws:
            # send session
            ws.send(json.dumps({"session_id": session_id, "sender": "user", "text": "__hello__"}))
            # reader/sender loop
            while True:
                # Drain outbound queue (non-blocking)
                try:
                    while True:
                        to_send = out_q.get_nowait()
                        ws.send(json.dumps(to_send))
                except queue.Empty:
                    pass
                # Blocking receive
                msg = ws.recv()
                if msg:
                    try:
                        data = json.loads(msg)
                    except Exception:
                        data = {"type": "raw", "payload": msg}
                    in_q.put(data)
    except Exception as e:
        in_q.put({"type": "error", "error": str(e)})

# Sidebar: configuration & upload artifacts
with st.sidebar:
    st.header("Artifacts")
    # Config block
    st.subheader("Configuration")
    st.session_state.backend_url = st.text_input("Backend URL", value=st.session_state.backend_url)
    # Keep WS URL derived unless user provided explicit env WS_URL
    derived_ws = _derive_ws_url(st.session_state.backend_url)
    st.session_state.ws_url = WS_URL_ENV or derived_ws
    # Health check
    health_placeholder = st.empty()
    try:
        h = requests.get(f"{st.session_state.backend_url}/healthz", timeout=2)
        if h.ok:
            health_placeholder.success("Backend reachable")
        else:
            health_placeholder.warning(f"Backend unhealthy: {h.status_code}")
    except Exception as e:
        health_placeholder.error(f"Backend unreachable: {e}")

    claim_id = st.text_input("Claim ID", value="demo-claim-1")
    # Connect controls
    if not st.session_state.ws_connected:
        if st.button("Connect Chat WebSocket"):
            st.session_state.ws_thread = threading.Thread(
                target=_ws_loop,
                args=(st.session_state.ws_url, st.session_state.session_id, st.session_state.ws_in_q, st.session_state.ws_out_q),
                daemon=True,
            )
            st.session_state.ws_thread.start()
            st.session_state.ws_connected = True
    else:
        st.success("WebSocket connected")
        st.caption(f"WS: {st.session_state.ws_url}")
        if st.button("Disconnect WS"):
            # Best-effort: mark as disconnected; thread will finish on error/close
            st.session_state.ws_connected = False
    img = st.file_uploader("Upload damage photo", type=["png", "jpg", "jpeg"])
    if img is not None:
        files = {"file": (img.name, img.read(), img.type)}
        res = requests.post(f"{st.session_state.backend_url}/api/upload/image", params={"claim_id": claim_id}, files=files, timeout=30)
        if res.ok:
            st.success("Image uploaded")
        else:
            st.error(f"Upload failed: {res.text}")
    tr = st.file_uploader("Upload call transcript", type=["txt", "vtt", "srt", "json"])
    if tr is not None:
        files = {"file": (tr.name, tr.read(), tr.type or "text/plain")}
        res = requests.post(f"{st.session_state.backend_url}/api/upload/transcript", params={"claim_id": claim_id}, files=files, timeout=30)
        if res.ok:
            st.success("Transcript uploaded")
        else:
            st.error(f"Upload failed: {res.text}")

# Chat interface
chat_container = st.container()
with chat_container:
    st.subheader("Live chat")
    if "messages" not in st.session_state:
        st.session_state.messages = []
    # Drain inbound WS queue
    drained = 0
    while True:
        try:
            evt = st.session_state.ws_in_q.get_nowait()
            drained += 1
            if evt.get("type") == "message":
                st.session_state.messages.append({"sender": evt.get("sender", "assistant"), "text": evt.get("text", "")})
            elif evt.get("type") == "session":
                # session ack
                pass
            elif evt.get("type") == "error":
                st.warning(f"WebSocket error: {evt.get('error')}")
                # Allow user to reconnect
                st.session_state.ws_connected = False
        except queue.Empty:
            break
    for m in st.session_state.messages:
        with st.chat_message(m["sender"]):
            st.markdown(m["text"]) 
    prompt = st.chat_input("Describe the incident or ask for claim status...")
    if prompt:
        st.session_state.messages.append({"sender": "user", "text": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        data = {"session_id": st.session_state.session_id, "sender": "user", "text": prompt}
        if st.session_state.ws_connected:
            st.session_state.ws_out_q.put(data)
        else:
            # fallback to REST
            try:
                res = requests.post(f"{st.session_state.backend_url}/api/chat", json=data, timeout=30)
                if res.ok:
                    reply = res.json().get("reply", "")
                else:
                    reply = f"Error: {res.text}"
            except Exception as e:
                reply = f"Network error: {e}"
            st.session_state.messages.append({"sender": "assistant", "text": reply})
            with st.chat_message("assistant"):
                st.markdown(reply)

# Incident summary panel (secured display)
with st.expander("Incident summary & artifacts", expanded=True):
    st.caption("Securely shows saved summaries, call transcripts, and images linked to claims.")
    st.write("Claim:", claim_id)
    # Fetch images
    try:
        imgs = requests.get(f"{st.session_state.backend_url}/api/claims/{claim_id}/images", timeout=10).json()
        if imgs:
            st.markdown("#### Photos")
            cols = st.columns(3)
            for i, it in enumerate(imgs[:6]):
                with cols[i % 3]:
                    st.image(it["url"], caption=it.get("created_at", ""))
    except Exception:
        pass
    # Transcripts list
    try:
        trs = requests.get(f"{st.session_state.backend_url}/api/claims/{claim_id}/transcripts", timeout=10).json()
        if trs:
            st.markdown("#### Transcripts")
            for t in trs[:10]:
                st.write("- ", t["url"])
    except Exception:
        pass
