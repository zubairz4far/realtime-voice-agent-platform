from __future__ import annotations

from server.app.tools import ToolExecutor


def test_lookup_order_known():
    executor = ToolExecutor()
    response = executor.execute("call-1", "lookup_order", {"order_id": "ORD-100001"})
    assert response.ok is True
    assert response.result == {
        "found": True,
        "order_id": "ORD-100001",
        "status": "shipped",
        "eta": "2 business days",
    }


def test_lookup_order_rejects_bad_shape():
    executor = ToolExecutor()
    response = executor.execute("call-1", "lookup_order", {"order_id": "../secret"})
    assert response.ok is False
    assert response.error == "invalid_tool_arguments"


def test_callback_is_idempotent_by_call_id():
    executor = ToolExecutor()
    args = {"customer_id": "CUS-100001", "preferred_window": "afternoon"}
    first = executor.execute("call-2", "schedule_callback", args)
    second = executor.execute("call-2", "schedule_callback", args)
    assert first.ok is True
    assert second.ok is True
    assert second.replayed is True
    assert second.result == first.result


def test_callback_rejects_unexpected_window():
    executor = ToolExecutor()
    response = executor.execute(
        "call-3",
        "schedule_callback",
        {"customer_id": "CUS-100001", "preferred_window": "midnight"},
    )
    assert response.ok is False
    assert response.error == "invalid_tool_arguments"
