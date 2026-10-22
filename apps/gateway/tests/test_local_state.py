from reflex_gateway.engine.deadline import Deadline
from reflex_gateway.engine.local_state import LocalState


def test_unseen_target_is_optimistic_and_failures_lower_health() -> None:
    st = LocalState(alpha=0.5)
    assert st.router_inputs("chat.reply") == {}
    st.on_attempt("a", "chat.reply", ok=False, quality_ok=False)
    inputs = st.router_inputs("chat.reply")["a"]
    assert inputs["health"] == 0.5
    assert inputs["quality"] == 0.5
    assert st.router_inputs("other.route") == {}


def test_quality_unknown_leaves_quality_untouched() -> None:
    st = LocalState(alpha=0.5)
    st.on_attempt("a", "r", ok=False, quality_ok=None)
    assert st.router_inputs("r")["a"]["quality"] == 1.0


def test_inflight_never_negative() -> None:
    st = LocalState()
    st.inflight_end("a", "r")
    st.inflight_start("a", "r")
    assert st.router_inputs("r")["a"]["inflight"] == 1


def test_deadline_gates_new_attempts() -> None:
    t = [0.0]
    d = Deadline(1000, now=lambda: t[0])
    assert d.allows(400)
    t[0] = 0.7
    assert round(d.remaining_ms()) == 300
    assert not d.allows(400)
    t[0] = 5.0
    assert d.remaining_ms() == 0.0
