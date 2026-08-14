import logging
import uuid
from typing import Any, Dict, Optional
import httpx
from app.config import settings

logger = logging.getLogger(__name__)


class EigiClient:
    """Client for triggering outbound calls and managing telephony with eigi.ai."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        agent_id: Optional[str] = None,
        base_url: Optional[str] = None,
        simulation_mode: Optional[bool] = None,
    ):
        self.api_key = api_key or settings.EIGI_API_KEY
        self.agent_id = agent_id or settings.EIGI_AGENT_ID
        self.base_url = (base_url or settings.EIGI_BASE_URL).rstrip("/")
        self.simulation_mode = simulation_mode if simulation_mode is not None else settings.SIMULATION_MODE

    async def start_call(
        self,
        to_number: str,
        variables: Dict[str, Any],
        agent_id: Optional[str] = None,
        webhook_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Trigger an outbound call to the customer via eigi.ai."""
        target_agent = agent_id or self.agent_id
        call_id = f"eigi_{uuid.uuid4().hex[:12]}"

        # If in simulation mode or API key is demo placeholder, handle gracefully
        if self.simulation_mode or not self.api_key or self.api_key.startswith("mock_"):
            logger.info(
                f"[EigiClient SIMULATION] Triggering simulated call {call_id} to {to_number} with agent {target_agent} and variables: {variables}"
            )
            return {
                "success": True,
                "status": "queued",
                "call_id": call_id,
                "agent_id": target_agent,
                "to_number": to_number,
                "variables": variables,
                "mode": "simulation",
                "message": "Call simulated successfully. Use /simulate-call or trigger simulator in UI to complete webhook flow.",
            }

        # Real API invocation to eigi.ai
        endpoint = f"{self.base_url}/calls/outbound"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "agent_id": target_agent,
            "to_number": to_number,
            "variables": variables,
        }
        if webhook_url:
            payload["webhook_url"] = webhook_url

        logger.info(f"[EigiClient] Dispatching real outbound call request to {endpoint} for {to_number}")
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(endpoint, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()
                return {
                    "success": True,
                    "status": data.get("status", "initiated"),
                    "call_id": data.get("call_id", call_id),
                    "data": data,
                    "mode": "live",
                }
        except httpx.HTTPStatusError as e:
            logger.error(f"[EigiClient] HTTP Error from eigi.ai: {e.response.status_code} - {e.response.text}")
            return {
                "success": False,
                "status": "failed",
                "error": f"eigi.ai returned status {e.response.status_code}: {e.response.text}",
                "call_id": call_id,
                "mode": "live",
            }
        except Exception as e:
            logger.error(f"[EigiClient] Failed to dispatch call to eigi.ai: {str(e)}")
            return {
                "success": False,
                "status": "failed",
                "error": str(e),
                "call_id": call_id,
                "mode": "live",
            }

    async def get_call_status(self, call_id: str) -> Dict[str, Any]:
        """Fetch real-time status of a call from eigi.ai."""
        if self.simulation_mode or not self.api_key or self.api_key.startswith("mock_"):
            return {
                "call_id": call_id,
                "status": "completed",
                "mode": "simulation",
            }

        endpoint = f"{self.base_url}/calls/{call_id}"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(endpoint, headers=headers)
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"[EigiClient] Failed to fetch call status for {call_id}: {e}")
            return {"call_id": call_id, "status": "unknown", "error": str(e)}


eigi_client = EigiClient()
