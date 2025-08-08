from typing import Optional
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
import os


class SQLStore:
    def __init__(self, server: str, database: str, user: Optional[str] = None, password: Optional[str] = None):
        self.server = server
        self.database = database
        self.user = user
        self.password = password
        self.engine: Optional[Engine] = None
        if server and database:
            conn_str = self._build_connection_string()
            self.engine = create_engine(conn_str, pool_pre_ping=True)

    def _build_connection_string(self) -> str:
        # Use ODBC Driver 18 for SQL Server (common on Azure)
        user = self.user or os.getenv("SQL_USER")
        password = self.password or os.getenv("SQL_PASSWORD")
        if user and password:
            return (
                f"mssql+pyodbc://{user}:{password}@{self.server}:1433/{self.database}?"
                "driver=ODBC+Driver+18+for+SQL+Server&Encrypt=yes&TrustServerCertificate=no&connection+timeout=30"
            )
        # Managed Identity / AAD can be added later (SQLAlchemy + azure-identity)
        # For now fall back to DSN-less without creds (might fail if not configured)
        return (
            f"mssql+pyodbc://@{self.server}:1433/{self.database}?"
            "driver=ODBC+Driver+18+for+SQL+Server&Encrypt=yes&TrustServerCertificate=no&connection+timeout=30"
        )

    async def link_image(self, claim_id: str, blob_url: str):
        if not self.engine:
            return
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO claim_images (claim_id, blob_url, created_at) VALUES (:cid, :url, SYSUTCDATETIME())"
                ),
                {"cid": claim_id, "url": blob_url},
            )

    async def link_transcript(self, claim_id: str, blob_url: str):
        if not self.engine:
            return
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO claim_transcripts (claim_id, blob_url, created_at) VALUES (:cid, :url, SYSUTCDATETIME())"
                ),
                {"cid": claim_id, "url": blob_url},
            )

    async def list_images(self, claim_id: str):
        if not self.engine:
            return []
        with self.engine.begin() as conn:
            res = conn.execute(text("SELECT blob_url, created_at FROM claim_images WHERE claim_id = :cid ORDER BY created_at DESC"), {"cid": claim_id})
            return [{"url": r[0], "created_at": str(r[1])} for r in res]

    async def list_transcripts(self, claim_id: str):
        if not self.engine:
            return []
        with self.engine.begin() as conn:
            res = conn.execute(text("SELECT blob_url, created_at FROM claim_transcripts WHERE claim_id = :cid ORDER BY created_at DESC"), {"cid": claim_id})
            return [{"url": r[0], "created_at": str(r[1])} for r in res]

    async def get_claim(self, claim_id: str):
        if not self.engine:
            # Local dev stub
            return {"claim_id": claim_id, "status": "pending"}
        with self.engine.begin() as conn:
            res = conn.execute(text("SELECT claim_id, status FROM claims WHERE claim_id = :cid"), {"cid": claim_id}).first()
            if not res:
                return {"claim_id": claim_id, "status": "unknown"}
            return {"claim_id": res[0], "status": res[1]}
