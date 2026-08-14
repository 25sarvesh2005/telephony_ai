import logging
import uuid
from typing import Any, Dict, List, Optional
import httpx
from app.config import settings

logger = logging.getLogger("eigi_client")


class EigiClient:
    """Official eigi.ai API Client for managing voice agents and outbound telephony."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        self.api_key = api_key or settings.EIGI_API_KEY
        base = (base_url or settings.EIGI_BASE_URL).rstrip("/")
        if not base.endswith("/public"):
            if "/v1" in base:
                self.base_url = f"{base}/public"
            else:
                self.base_url = f"{base}/v1/public"
        else:
            self.base_url = base

    def _get_headers(self) -> Dict[str, str]:
        return {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json",
        }

    async def start_call(
        self,
        to_number: str,
        from_number: Optional[str] = None,
        variables: Optional[Dict[str, Any]] = None,
        agent_id: Optional[str] = None,
        telephony_provider: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Triggers an outbound conversational AI voice call to a customer's phone number.
        Uses POST /v1/public/calls/outbound with schema:
        {
          "agent_id": "...",
          "params": [{ "mobile_number": "+91...", "metadata": { ... } }],
          "telephony_provider": "PLIVO"
        }
        """
        active_agent_id = agent_id or settings.EIGI_AGENT_ID
        active_provider = telephony_provider or settings.EIGI_TELEPHONY_PROVIDER

        if settings.SIMULATION_MODE or self.api_key.startswith("mock_"):
            logger.info(f"[SIMULATION] Simulating outbound call to {to_number} via eigi agent {active_agent_id}")
            simulated_call_id = f"sim_{uuid.uuid4().hex[:12]}"
            return {
                "success": True,
                "status": "queued",
                "call_id": simulated_call_id,
                "provider": active_provider,
                "agent_id": active_agent_id,
                "to_number": to_number,
                "message": "Call simulated (SANDBOX MODE)",
                "mode": "simulation",
            }

        endpoint = f"{self.base_url}/calls/outbound"
        param_item: Dict[str, Any] = {"mobile_number": to_number}
        if variables:
            param_item["metadata"] = variables

        payload: Dict[str, Any] = {
            "agent_id": active_agent_id,
            "params": [param_item],
            "telephony_provider": active_provider,
        }

        logger.info(f"Dispatching eigi.ai outbound call to {to_number} (Endpoint: {endpoint})")
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    endpoint,
                    json=payload,
                    headers=self._get_headers(),
                )

                if response.status_code in (200, 201):
                    data = response.json()
                    logger.info(f"eigi.ai outbound call queued successfully: {data}")
                    return {
                        "success": True,
                        "status": "queued",
                        "call_id": data.get("conversation_id") or data.get("call_id") or f"eigi_{uuid.uuid4().hex[:12]}",
                        "provider": active_provider,
                        "agent_id": active_agent_id,
                        "to_number": to_number,
                        "data": data,
                        "mode": "live",
                        "message": data.get("message", "Outbound calls initiated: 1 successful"),
                    }
                else:
                    error_msg = f"eigi.ai returned status {response.status_code}: {response.text}"
                    logger.error(error_msg)
                    return {
                        "success": False,
                        "status": "failed",
                        "error": error_msg,
                        "status_code": response.status_code,
                        "response_body": response.text,
                    }

        except Exception as e:
            logger.error(f"Failed to connect to eigi.ai API: {e}", exc_info=True)
            return {
                "success": False,
                "status": "error",
                "error": str(e),
            }

    async def get_call_status(self, conversation_id: str) -> Dict[str, Any]:
        endpoint = f"{self.base_url}/conversations/{conversation_id}"
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(endpoint, headers=self._get_headers())
                if response.status_code == 200:
                    return response.json()
                return {"status": "unknown", "status_code": response.status_code, "body": response.text}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def get_agent(self, agent_id: Optional[str] = None) -> Dict[str, Any]:
        target_id = agent_id or settings.EIGI_AGENT_ID
        endpoint = f"{self.base_url}/agents/{target_id}"
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(endpoint, headers=self._get_headers())
                if response.status_code == 200:
                    return response.json()
                return {"error": response.text, "status_code": response.status_code}
        except Exception as e:
            return {"error": str(e)}

    async def list_conversations(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Fetch recent conversations and call transcripts from eigi.ai API."""
        endpoint = f"{self.base_url}/conversations"
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(endpoint, headers=self._get_headers())
                if response.status_code == 200:
                    data = response.json()
                    return data.get("data", [])
                logger.warning(f"Failed to list eigi conversations: {response.status_code} - {response.text}")
                return []
        except Exception as e:
            logger.error(f"Error fetching eigi conversations: {e}")
            return []


eigi_client = EigiClient()


