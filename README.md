# Insurance Multi-Agent (AKS)

End-to-end scaffold for a motor car insurance claim handling system with:
- Streamlit + Azure Web PubSub (frontend)
- FastAPI + Azure Web PubSub + Cosmos DB + Azure SQL + Blob Storage (backend)
- Deployable on Azure Kubernetes Service (AKS)

This is a minimal, working scaffold with sample flows for:
- CreateClaim + ProcessClaim job
- UserInputRequested → resume continuation
- Real-time UI updates via Web PubSub

See `src/backend/README.md` and `src/frontend/README.md` for run/deploy steps.

## Run locally

Backend
- pip install -r src/backend/requirements.txt
- uvicorn src.backend.app.main:app --host 0.0.0.0 --port 8000 --reload
- Open http://localhost:8000/docs for Swagger UI

Frontend
- pip install streamlit requests
- streamlit run src/frontend/streamlit_app.py

Environment variables
- WEBPUBSUB_CONNECTION_STRING
- WEBPUBSUB_HUB (default: claims)
- COSMOS_URL, COSMOS_KEY, COSMOS_DB (claimsdb), COSMOS_CONTAINER (conversations)
- SQL_SERVER, SQL_DATABASE, SQL_USER, SQL_PASSWORD
- BLOB_CONNECTION_STRING, BLOB_CONTAINER (claim-artifacts)
