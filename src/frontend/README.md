# Frontend (Streamlit)

A Streamlit UI that:
- Provides a chat interface.
- Uploads images/transcripts to the backend.
- Displays incident summary and artifacts (placeholder fetch).

Run locally:
- Install: `pip install streamlit requests`
- Launch: `streamlit run src/frontend/streamlit_app.py`

Env:
- BACKEND_URL (default http://localhost:8000)
- WS_URL (default ws://localhost:8000/ws)
