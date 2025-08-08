from typing import Optional
from azure.storage.blob import BlobServiceClient
import uuid


class BlobStore:
    def __init__(self, connection_string: str, container: str):
        self.client = BlobServiceClient.from_connection_string(connection_string) if connection_string else None
        self.container = container
        if self.client:
            try:
                self.client.create_container(container)
            except Exception:
                pass

    async def upload_file(self, file) -> str:
        if not self.client:
            # return dummy URL in local dev
            return f"https://example.local/{uuid.uuid4()}-{file.filename}"
        blob_name = f"{uuid.uuid4()}-{file.filename}"
        blob_client = self.client.get_blob_client(self.container, blob_name)
        data = await file.read()
        blob_client.upload_blob(data, overwrite=True)
        return blob_client.url
