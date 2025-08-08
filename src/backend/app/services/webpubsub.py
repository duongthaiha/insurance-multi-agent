from typing import Optional
import json
from azure.messaging.webpubsubservice import WebPubSubServiceClient


class WebPubSubHub:
    def __init__(self, connection_string: str, hub: str):
        self.client = WebPubSubServiceClient.from_connection_string(connection_string, hub=hub) if connection_string else None
        self.hub = hub

    def can_broadcast(self) -> bool:
        return self.client is not None

    async def send_to_all(self, event: str, data: dict):
        if not self.client:
            return
        payload = json.dumps({"event": event, "data": data})
        # SDK is sync; keep it simple
        self.client.send_to_all(content=payload, content_type="application/json")

    async def get_client_access_token(self, user_id: Optional[str] = None) -> dict:
        if not self.client:
            return {"url": "", "token": ""}
        token = self.client.get_client_access_token(user_id=user_id)
        return token  # {'url':..., 'token':...}
