from __future__ import annotations

import re
import threading
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from server.app.models import ToolCallResponse

ORDER_ID = re.compile(r"^ORD-[0-9]{6}$")


class LookupOrderArgs(BaseModel):
    order_id: str = Field(min_length=10, max_length=10)


class ScheduleCallbackArgs(BaseModel):
    customer_id: str = Field(pattern=r"^CUS-[0-9]{6}$")
    preferred_window: str = Field(pattern=r"^(morning|afternoon|evening)$")


class ToolExecutor:
    def __init__(self) -> None:
        self._callbacks: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._orders = {
            "ORD-100001": {"status": "shipped", "eta": "2 business days"},
            "ORD-100002": {"status": "processing", "eta": "4 business days"},
        }

    def execute(self, call_id: str, name: str, arguments: dict[str, Any]) -> ToolCallResponse:
        try:
            if name == "lookup_order":
                args = LookupOrderArgs.model_validate(arguments)
                if not ORDER_ID.fullmatch(args.order_id):
                    return ToolCallResponse(
                        call_id=call_id, ok=False, error="invalid_tool_arguments"
                    )
                order = self._orders.get(args.order_id)
                result = (
                    {"found": False, "order_id": args.order_id}
                    if order is None
                    else {"found": True, "order_id": args.order_id, **order}
                )
                return ToolCallResponse(call_id=call_id, ok=True, result=result)

            if name == "schedule_callback":
                args = ScheduleCallbackArgs.model_validate(arguments)
                with self._lock:
                    existing = self._callbacks.get(call_id)
                    if existing is not None:
                        return ToolCallResponse(
                            call_id=call_id,
                            ok=True,
                            result=existing,
                            replayed=True,
                        )
                    result = {
                        "callback_id": f"CB-{len(self._callbacks) + 1:06d}",
                        "customer_id": args.customer_id,
                        "preferred_window": args.preferred_window,
                        "status": "scheduled",
                    }
                    self._callbacks[call_id] = result
                return ToolCallResponse(call_id=call_id, ok=True, result=result)
        except ValidationError:
            return ToolCallResponse(call_id=call_id, ok=False, error="invalid_tool_arguments")

        return ToolCallResponse(call_id=call_id, ok=False, error="tool_not_allowed")
