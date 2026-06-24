from __future__ import annotations

import pytest

from ops_board_observe import bootstrap_observability, observe
from ops_board_observe.instrumentation import _otlp_signal_endpoint, _reset_for_tests


def test_otlp_signal_endpoint_adds_signal_suffix() -> None:
    assert _otlp_signal_endpoint("http://hp-15:4318", "traces") == "http://hp-15:4318/v1/traces"
    assert _otlp_signal_endpoint("http://hp-15:4318/", "logs") == "http://hp-15:4318/v1/logs"
    assert _otlp_signal_endpoint("http://hp-15:4318/v1/traces", "traces") == "http://hp-15:4318/v1/traces"


def test_bootstrap_returns_settings_with_export_disabled() -> None:
    _reset_for_tests()

    settings = bootstrap_observability(
        export=False,
        service_name="unit-service",
        service_namespace="unit-namespace",
        owner="unit-owner",
        otlp_endpoint="http://hp-15:4318",
    )

    assert settings.service_name == "unit-service"
    assert settings.service_namespace == "unit-namespace"
    assert settings.owner == "unit-owner"
    assert settings.otlp_endpoint == "http://hp-15:4318"


def test_observe_returns_wrapped_function_result() -> None:
    @observe("unit.success")
    def add(left: int, right: int) -> int:
        return left + right

    assert add(2, 3) == 5


def test_observe_records_and_reraises_exceptions() -> None:
    @observe("unit.failure")
    def fail() -> None:
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        fail()


@pytest.mark.asyncio
async def test_observe_supports_async_functions() -> None:
    @observe("unit.async")
    async def async_add(left: int, right: int) -> int:
        return left + right

    assert await async_add(2, 4) == 6
