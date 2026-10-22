from datetime import UTC, datetime, timedelta

from reflex_mongo.pipelines import (
    a08_first_bad_at,
    a09_signature,
    a10_similar_incidents,
    a11_side_diagnosis,
    a12_top_contributors,
    a13_blast_radius,
)


def test_a08_first_bad_at_build() -> None:
    now = datetime.now(tz=UTC)
    pipeline = a08_first_bad_at.build(
        scope="target",
        key="vendorA:large",
        detected_at=now,
        budget=0.01,
    )
    assert len(pipeline) == 6
    assert "$match" in pipeline[0]
    assert "$setWindowFields" in pipeline[2]
    assert pipeline[3]["$match"]["bad"] is True


def test_a09_signature_build() -> None:
    now = datetime.now(tz=UTC)
    pipeline = a09_signature.build(
        scope="target",
        key="vendorA:large",
        detected_at=now,
    )
    assert len(pipeline) == 7
    assert "$densify" in pipeline[1]
    assert "$fill" in pipeline[2]
    assert "$set" in pipeline[3]
    assert "vec" in pipeline[6]["$project"]


def test_a10_similar_incidents_build() -> None:
    dummy_vec = [0.0] * 64
    pipeline = a10_similar_incidents.build(
        vec=dummy_vec,
        sli="quality",
        k=5,
    )
    assert len(pipeline) == 8
    assert "$vectorSearch" in pipeline[0]
    assert pipeline[0]["$vectorSearch"]["index"] == "incident_signature"
    assert "$lookup" in pipeline[3]


def test_a11_side_diagnosis_build() -> None:
    now = datetime.now(tz=UTC)
    pipeline = a11_side_diagnosis.build(
        target="vendorA:large",
        from_=now - timedelta(minutes=5),
        to=now,
    )
    assert len(pipeline) == 4
    assert pipeline[1]["$group"]["_id"] == "$meta.path"
    assert "$percentile" in pipeline[1]["$group"]["p95"]


def test_a12_top_contributors_build() -> None:
    now = datetime.now(tz=UTC)
    pipeline = a12_top_contributors.build(
        target="vendorA:large",
        from_=now - timedelta(minutes=10),
        to=now,
        k=3,
    )
    assert len(pipeline) == 2
    facet = pipeline[1]["$facet"]
    assert "by_route" in facet
    assert "by_outcome" in facet
    assert "by_finish" in facet


def test_a13_blast_radius_build() -> None:
    now = datetime.now(tz=UTC)
    pipeline = a13_blast_radius.build(
        from_=now - timedelta(minutes=10),
        to=now,
        route="order.extract",
    )
    assert len(pipeline) == 4
    assert pipeline[1]["$group"]["_id"] == "$session"
    assert "saved_by_reflex" in pipeline[2]["$group"]
