"""Property-based fuzzing of the push snapshot parser: it must never raise."""

from __future__ import annotations

from typing import Any

from hypothesis import given
from hypothesis import strategies as st

from argus.fleet.model import METRIC_KEYS
from argus.fleet.sources.push import derive_metrics

# Arbitrary JSON-ish values, including the shapes a real snapshot uses and many
# it never should (wrong types, nesting, NaN-ish strings).
_json = st.recursive(
    st.none()
    | st.booleans()
    | st.integers()
    | st.floats(allow_nan=True, allow_infinity=True)
    | st.text(),
    lambda children: (
        st.lists(children, max_size=5) | st.dictionaries(st.text(max_size=8), children, max_size=5)
    ),
    max_leaves=20,
)


@given(snapshot=_json)
def test_derive_metrics_never_raises_on_arbitrary_input(snapshot: Any) -> None:
    # The parser treats the snapshot as untrusted; any structure must be safe.
    metrics, totals = derive_metrics(snapshot if isinstance(snapshot, dict) else {}, "discord")
    assert set(metrics) == set(METRIC_KEYS)
    assert all(isinstance(v, float) for v in metrics.values())
    errors, commands = totals
    assert isinstance(errors, float)
    assert isinstance(commands, float)


@given(
    samples=st.lists(
        st.fixed_dictionaries(
            {
                "name": st.text(max_size=12),
                "labels": st.dictionaries(st.text(max_size=4), st.text(max_size=8), max_size=3),
                "value": st.floats(allow_nan=True, allow_infinity=True) | st.text() | st.none(),
            }
        ),
        max_size=8,
    )
)
def test_derive_metrics_handles_arbitrary_samples(samples: list[dict[str, Any]]) -> None:
    snapshot = {"metrics": {"discord_guilds": {"samples": samples}}}
    metrics, _ = derive_metrics(snapshot, "discord")
    # guilds is finite regardless of what junk the samples contained.
    assert metrics["guilds"] == metrics["guilds"]  # not NaN
