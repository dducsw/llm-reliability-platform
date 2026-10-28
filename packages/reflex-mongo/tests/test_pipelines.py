from datetime import UTC, datetime, timedelta

from reflex_mongo.pipelines import (
    a04_burn_rate,
    a05_budget_remaining,
    a06_anomaly,
    a07_probe_blindness,
    a08_first_bad_at,
    a09_signature,
    a10_similar_incidents,
    a11_side_diagnosis,
    a12_top_contributors,
    a13_blast_radius,
    a16_recovery_proof,
    a17_mttx,
    a18_cost_daily,
)


def test_a04_burn_rate_build() -> None:
    now = datetime.now(tz=UTC)
    pipeline = a04_burn_rate.build(now=now, scope="target", keys=["vendorA:large"])
    assert len(pipeline) == 3
    assert "$match" in pipeline[0]
    assert "$group" in pipeline[1]
    assert "t_short" in pipeline[1]["$group"]
    assert "b_short" in pipeline[1]["$group"]


def test_a05_budget_remaining_build() -> None:
    now = datetime.now(tz=UTC)
    pipeline = a05_budget_remaining.build(
        now=now,
        scope="target",
        key="vendorA:large",
        budget=0.01,
    )
    assert len(pipeline) == 4
    assert "$match" in pipeline[0]
    assert "$unionWith" in pipeline[1]
    assert pipeline[1]["$unionWith"]["coll"] == "sli_1m"
    assert "$group" in pipeline[2]
    assert "remaining" in pipeline[3]["$project"]


def test_a06_anomaly_build() -> None:
    now = datetime.now(tz=UTC)
    pipeline = a06_anomaly.build(
        now=now,
        scope="target",
        key="vendorA:large",
        z_threshold=3.0,
    )
    assert len(pipeline) == 7
    assert "$match" in pipeline[0]
    assert "$setWindowFields" in pipeline[1]
    assert "sd" in pipeline[1]["$setWindowFields"]["output"]
    assert "ewma" in pipeline[1]["$setWindowFields"]["output"]
    assert pipeline[4]["$match"]["z"]["$gte"] == 3.0


def test_a07_probe_blindness_build() -> None:
    now = datetime.now(tz=UTC)
    pipeline = a07_probe_blindness.build(now=now, lookback_minutes=10)
    assert len(pipeline) == 9
    assert "$match" in pipeline[0]
    assert "$densify" in pipeline[3]
    assert "$fill" in pipeline[4]
    assert pipeline[5]["$match"]["n"] == 0
    assert "silent_minutes" in pipeline[7]["$project"]


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


def test_a16_recovery_proof_build() -> None:
    now = datetime.now(tz=UTC)
    pipeline = a16_recovery_proof.build(
        key="order.extract",
        baseline=(now - timedelta(minutes=15), now - timedelta(minutes=5)),
        after=(now, now + timedelta(minutes=5)),
    )
    assert len(pipeline) == 2
    assert "$match" in pipeline[0]
    assert "$facet" in pipeline[1]
    assert "baseline" in pipeline[1]["$facet"]
    assert "after" in pipeline[1]["$facet"]


def test_a17_mttx_build() -> None:
    now = datetime.now(tz=UTC)
    pipeline = a17_mttx.build(
        from_=now - timedelta(days=7),
        to=now,
        sli="quality",
    )
    assert len(pipeline) == 4
    assert "$match" in pipeline[0]
    assert "$set" in pipeline[1]
    assert "mttd_s" in pipeline[1]["$set"]
    assert "mttr_s" in pipeline[1]["$set"]
    assert "$group" in pipeline[2]
    assert "$project" in pipeline[3]


def test_a18_cost_daily_build() -> None:
    now = datetime.now(tz=UTC)
    pipeline = a18_cost_daily.build(
        from_=now - timedelta(days=30),
        to=now,
    )
    assert len(pipeline) == 4
    assert "$match" in pipeline[0]
    assert "$group" in pipeline[1]
    assert "$sort" in pipeline[2]
    assert "$project" in pipeline[3]
