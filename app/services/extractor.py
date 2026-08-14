import json
import logging
import re
from typing import Any, Dict, Optional, Union
from app.config import settings
from app.schemas import ExtractedIntent

logger = logging.getLogger(__name__)


class IntentExtractor:
    """Extracts structured intent from eigi.ai payload or raw transcript."""

    def extract_from_payload(
        self,
        payload_intent: Optional[Union[ExtractedIntent, Dict[str, Any]]] = None,
        transcript: Optional[str] = None,
        order_id: Optional[str] = None,
    ) -> ExtractedIntent:
        """Processes payload-provided intent or falls back to transcript parsing."""
        if payload_intent:
            if isinstance(payload_intent, ExtractedIntent):
                return payload_intent
            if isinstance(payload_intent, dict) and payload_intent.get("customer_intent"):
                try:
                    return ExtractedIntent(
                        order_id=payload_intent.get("order_id") or order_id,
                        call_outcome=payload_intent.get("call_outcome", "reached"),
                        customer_intent=payload_intent.get("customer_intent", "unclear"),
                        reschedule_datetime=payload_intent.get("reschedule_datetime"),
                        updated_address=payload_intent.get("updated_address"),
                        notes=payload_intent.get("notes"),
                        confidence=float(payload_intent.get("confidence", 0.95)),
                    )
                except Exception as e:
                    logger.warning(f"Error parsing raw extracted_intent dict: {e}, falling back to transcript")

        # Fallback to transcript extraction
        if transcript:
            return self.extract_from_transcript(transcript, order_id=order_id)

        # Default fallback if no data provided
        return ExtractedIntent(
            order_id=order_id,
            call_outcome="failed",
            customer_intent="unclear",
            notes="No transcript or structured intent provided in webhook.",
            confidence=0.0,
        )

    def extract_from_transcript(self, transcript: str, order_id: Optional[str] = None) -> ExtractedIntent:
        """Deterministic rule-based NLP extraction with optional LLM fallback."""
        text = transcript.lower()

        # Check for non-contact outcomes
        if any(term in text for term in ["voicemail", "leave a message", "tone after the beep", "answering machine"]):
            return ExtractedIntent(
                order_id=order_id,
                call_outcome="voicemail",
                customer_intent="no_answer",
                notes="Call went to voicemail / answering machine.",
                confidence=0.9,
            )

        if any(term in text for term in ["no answer", "busy signal", "did not pick up", "unreachable"]):
            return ExtractedIntent(
                order_id=order_id,
                call_outcome="no_answer",
                customer_intent="no_answer",
                notes="Customer did not answer.",
                confidence=0.9,
            )

        # Check for Cancellation
        cancel_patterns = [
            r"\b(cancel|cancelled|cancellation)\b",
            r"don'?t want (it|the order|this anymore)",
            r"bought (it )?somewhere else",
            r"refuse (delivery|order)",
            r"no longer need",
            r"refund",
        ]
        if any(re.search(p, text) for p in cancel_patterns):
            notes = "Customer requested cancellation."
            if "somewhere else" in text or "found other" in text:
                notes = "Customer purchased from alternative source."
            return ExtractedIntent(
                order_id=order_id,
                call_outcome="reached",
                customer_intent="cancel",
                notes=notes,
                confidence=0.92,
            )

        # Check for Wrong / Update Address
        address_patterns = [
            r"wrong address",
            r"new address",
            r"change (my|the) address",
            r"deliver (to|at) (a )?different",
            r"moved to",
            r"address is incorrect",
        ]
        if any(re.search(p, text) for p in address_patterns):
            # Try to capture updated address mention if any
            addr_match = re.search(r"(?:to|at|address is)\s+([0-9a-zA-Z\s,.-]{10,60})", transcript, re.IGNORECASE)
            updated_addr = addr_match.group(1).strip() if addr_match else None
            return ExtractedIntent(
                order_id=order_id,
                call_outcome="reached",
                customer_intent="wrong_address",
                updated_address=updated_addr,
                notes="Customer indicated address was incorrect or requested new location.",
                confidence=0.88,
            )

        # Check for Human Escalation / Agent
        escalate_patterns = [
            r"human",
            r"real person",
            r"customer service",
            r"representative",
            r"manager",
            r"speak to someone",
            r"talk to an agent",
        ]
        if any(re.search(p, text) for p in escalate_patterns):
            return ExtractedIntent(
                order_id=order_id,
                call_outcome="reached",
                customer_intent="escalate_human",
                notes="Customer requested to speak with a human support representative.",
                confidence=0.95,
            )

        # Check for Reschedule
        reschedule_patterns = [
            r"\b(reschedule|deliver tomorrow|deliver on|bring it on|try again|deliver later|after 6|weekend)\b",
            r"wasn'?t (at )?home",
            r"was away",
            r"out of station",
            r"deliver next",
        ]
        if any(re.search(p, text) for p in reschedule_patterns):
            # Extract time/date phrase
            date_match = re.search(
                r"(?:tomorrow|next monday|next tuesday|next wednesday|next thursday|next friday|next saturday|next sunday|this weekend|monday|tuesday|wednesday|thursday|friday|saturday|sunday)(?:\s+(?:morning|evening|afternoon|at\s+\d+\s*(?:am|pm)?))?",
                text,
            )
            reschedule_dt = date_match.group(0) if date_match else "Tomorrow"
            return ExtractedIntent(
                order_id=order_id,
                call_outcome="reached",
                customer_intent="reschedule",
                reschedule_datetime=reschedule_dt.title(),
                notes=f"Customer requested reschedule for: {reschedule_dt.title()}.",
                confidence=0.85,
            )

        # If nothing matches clearly, classify as unclear / escalate
        return ExtractedIntent(
            order_id=order_id,
            call_outcome="reached",
            customer_intent="unclear",
            notes="Customer intent could not be unambiguously categorized from transcript.",
            confidence=0.4,
        )


intent_extractor = IntentExtractor()
