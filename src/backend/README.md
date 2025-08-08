# Backend (FastAPI)

This FastAPI app exposes:
- WebSocket `/ws` for real-time chat.
- REST endpoints to upload images and transcripts, resume jobs, and fetch job state and conversation history.

It integrates with Azure services:
- Azure Web PubSub (broadcasts and client token issuance)
- Azure Cosmos DB (conversation history + job state)
- Azure Blob Storage (images + transcripts)
- Azure SQL Database (structured claim data and links to blobs)

Environment variables:
- WEBPUBSUB_CONNECTION_STRING
- WEBPUBSUB_HUB (default: claims)
- COSMOS_URL, COSMOS_KEY, COSMOS_DB (claimsdb), COSMOS_CONTAINER (conversations)
- SQL_SERVER, SQL_DATABASE, SQL_USER, SQL_PASSWORD
- BLOB_CONNECTION_STRING, BLOB_CONTAINER (claim-artifacts)

Run locally:
- Install deps: `pip install -r src/backend/requirements.txt`
- Start API: `uvicorn src.backend.app.main:app --host 0.0.0.0 --port 8000 --reload`

AKS notes:
- Build a container with this app, set env vars via Kubernetes Secret and ConfigMap.
- Expose via Ingress and secure with HTTPS.
