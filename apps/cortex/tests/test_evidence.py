from reflex_core.incident import Evidence, Hypothesis, ToolStep
from reflex_cortex.evidence import validate


def test_validate_valid_evidence() -> None:
    hypotheses = [
        Hypothesis(
            id="H1",
            statement="Output truncation",
            confidence=0.85,
            evidence=[Evidence(type="metric", ref="q_01", claim="high burn")],
        )
    ]
    steps = [ToolStep(n=1, tool="mongo.run_pipeline", args={}, ms=10.0, result_ref="q_01")]
    results = {"q_01": {"burn": 30.0}}

    val = validate(hypotheses, steps, results)
    assert len(val) == 1
    assert val[0].confidence == 0.85


def test_validate_invalid_ref_reduces_confidence() -> None:
    hypotheses = [
        Hypothesis(
            id="H2",
            statement="Hallucinated hypothesis",
            confidence=0.90,
            evidence=[Evidence(type="metric", ref="non_existent_ref", claim="fake claim")],
        )
    ]
    val = validate(hypotheses, steps=[], results={})
    assert len(val) == 1
    # Bị hạ confidence vì ref không tồn tại
    assert val[0].confidence <= 0.45
