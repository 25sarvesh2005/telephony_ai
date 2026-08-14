# eigi.ai Agent Setup & Configuration Guide

This document contains the prompt, structured schema, and telephony connection guidelines to configure your voice agent on [eigi.ai](https://eigi.ai).

---

## 1. Voice Agent Prompt (System Prompt)

Copy and paste this into the **System Prompt** field in your eigi.ai dashboard:

```text
You are an empathetic, efficient AI customer service assistant calling on behalf of {{merchant_name}} regarding order #{{order_id}}.

Context:
- Customer Name: {{customer_name}}
- Order Value: {{amount}}
- Delivery attempts so far: {{delivery_attempts}}
- City: {{city}}

Key Instructions:
1. Regulatory & Disclosure:
   - Start immediately with: "Hello {{customer_name}}, this is an automated AI call from {{merchant_name}} regarding your Cash on Delivery order #{{order_id}}. This call is recorded for quality purposes."
2. Purpose:
   - State that the delivery partner attempted delivery today but was unable to reach them.
3. Inquiry:
   - Ask why delivery failed and whether they would like to:
     a) Reschedule for a specific day/time (e.g. tomorrow morning/evening).
     b) Cancel the order (if they no longer want it or bought elsewhere).
     c) Correct or update the delivery address.
4. Active Confirmation:
   - Confirm their preference back clearly (e.g. "Got it, I have noted that you would like delivery rescheduled for tomorrow evening after 6 PM").
5. Politeness:
   - Keep answers short, conversational, and courteous. End with a polite closing.
```

---

## 2. Structured Output Extraction Schema

In eigi.ai's **Functions / Structured Output** section, register the following JSON schema:

```json
{
  "name": "extract_call_outcome",
  "description": "Extract structured intent and details from the completed recovery call",
  "parameters": {
    "type": "object",
    "properties": {
      "order_id": {
        "type": "string",
        "description": "The merchant order ID being discussed"
      },
      "call_outcome": {
        "type": "string",
        "enum": ["reached", "no_answer", "voicemail", "busy", "failed"],
        "description": "Whether customer was reached or went to voicemail/no answer"
      },
      "customer_intent": {
        "type": "string",
        "enum": ["reschedule", "cancel", "wrong_address", "unclear", "escalate_human", "no_answer"],
        "description": "Primary intent resolved during call"
      },
      "reschedule_datetime": {
        "type": "string",
        "nullable": true,
        "description": "Specific date/time requested for redelivery (e.g. 'Tomorrow at 6:00 PM')"
      },
      "updated_address": {
        "type": "string",
        "nullable": true,
        "description": "New address provided by customer if address was incorrect"
      },
      "notes": {
        "type": "string",
        "description": "Concise summary of customer's response"
      },
      "confidence": {
        "type": "number",
        "description": "Confidence score between 0.0 and 1.0"
      }
    },
    "required": ["order_id", "call_outcome", "customer_intent"]
  }
}
```

---

## 3. Webhook Configuration

Set your eigi.ai Agent's Webhook URL to:

```text
https://<YOUR_NGROK_SUBDOMAIN>.ngrok-free.app/webhooks/eigi/call-completed
```

Events: `Call Completed` / `Session Ended`.

---

## 4. Telephony Provider (Twilio / Plivo)

1. In eigi.ai -> **Integrations** -> Select **Twilio** (or **Plivo**).
2. Enter your `Account SID` and `Auth Token`.
3. Select an outbound Caller ID phone number purchased in your Twilio/Plivo console.
