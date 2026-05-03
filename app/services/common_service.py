"""Small cross-cutting helpers used across services."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from enum import Enum

class LLMResponseType(str, Enum):
    TOOL_CALL = "tool_calls"
    MESSAGE   = "stop"
    

def parse_llm_response(response: dict) -> tuple[LLMResponseType, any]:
    """Returns (response_type, payload).
    
    - TOOL_CALL -> list of {"name": str, "args": dict, "id": str}
    - MESSAGE   -> str content
    """
    choice       = response["choices"][0]
    finish_reason = choice["finish_reason"]
    message      = choice["message"]

    if finish_reason == "tool_calls":
        tool_calls = [
            {
                "id":   tc["id"],
                "name": tc["function"]["name"],
                "args": json.loads(tc["function"]["arguments"]),
            }
            for tc in message.get("tool_calls", [])
        ]
        return LLMResponseType.TOOL_CALL, tool_calls

    return LLMResponseType.MESSAGE, message.get("content", "")


def new_uuid() -> str:
    """Return a fresh UUIDv4 as a string."""
    return str(uuid.uuid4())


def utc_now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()
