from reflex_telemetry import llmobs


def test_span_is_noop_when_llmobs_disabled() -> None:
    assert not llmobs.enabled()
    with llmobs.span("tool", "dd.logs_search") as s:
        assert s is None
        llmobs.annotate(s, input_data={"q": 1}, output_data="x")


def test_span_records_when_enabled() -> None:
    from ddtrace.llmobs import LLMObs

    LLMObs.enable(
        agent_service="reflex-test", agentless_enabled=True, api_key="x", site="datadoghq.com"
    )
    try:
        with llmobs.span("agent", "cortex.investigate") as a:
            assert a is not None
            with llmobs.span("tool", "dd.logs_search") as t:
                llmobs.annotate(t, input_data={"q": "service:x"}, output_data="0 logs")
            llmobs.annotate(a, tags={"incident_id": "INC-1"})
            exported = LLMObs.export_span(a)
            assert exported and exported["span_id"]
    finally:
        LLMObs.disable()
