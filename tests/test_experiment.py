"""Scenario reproducibility and missing-quote handling in research metrics."""

import numpy as np
import pytest

from experiment import REGIMES, summarize
from lob_sim.data import run_simulation


@pytest.mark.parametrize("config", REGIMES.values(), ids=REGIMES.keys())
def test_regime_reproducibility(config):
    first = run_simulation(seed=42, **config)
    second = run_simulation(seed=42, **config)
    assert first["snapshots"] == second["snapshots"]
    fills = lambda r: [(t.price, t.quantity, t.aggressor_side) for t in r["book"].trades]
    assert fills(first) == fills(second)
    assert all(s["best_bid"] < s["best_ask"] for s in first["snapshots"])
    if not config:
        assert len(first["book"].trades) == 212
        assert set(first["midprices"]) == {100.0}


def test_summary_does_not_fill_missing_quotes_or_bridge_returns():
    result = run_simulation(n_events=3)
    result["snapshots"] = [
        {"midprice": 100.0, "spread": 0.1, "bids": [(99.95, 10)], "asks": [(100.05, 10)]},
        {"midprice": None, "spread": None, "bids": [(99.95, 10)], "asks": []},
        {"midprice": 101.0, "spread": 0.2, "bids": [(100.9, 10)], "asks": [(101.1, 10)]},
    ]
    row, (mid, _, _) = summarize("Baseline", result)
    assert np.isnan(mid[1])
    assert row["mean_spread"] == pytest.approx(0.15)
    assert row["two_sided_quote_pct"] == pytest.approx(200 / 3)
    assert row["valid_return_pairs"] == 1
    assert np.isnan(row["volatility_bps_per_event"])


@pytest.mark.parametrize("config", [
    {"liquidity_scale": 0}, {"market_probability": 0.98},
    {"market_size_scale": float("nan")}, {"market_buy_probability": -0.1},
])
def test_invalid_flow_configuration(config):
    with pytest.raises(ValueError):
        run_simulation(**config)


@pytest.mark.parametrize("config", [*REGIMES.values(), {"market_probability": 0.97}],
                         ids=[*REGIMES, "depleted-book"])
def test_snapshot_reuse_matches_original_metric_path(config):
    from benchmark import fingerprint

    reference = run_simulation(n_events=500, seed=7, reuse_snapshot_metrics=False, **config)
    optimized = run_simulation(n_events=500, seed=7, reuse_snapshot_metrics=True, **config)
    assert fingerprint(reference) == fingerprint(optimized)
