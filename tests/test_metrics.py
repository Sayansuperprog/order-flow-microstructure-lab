"""Synthetic-only metrics tests: imbalance, microprice, forward-return study."""

import pytest

from lob_sim.data import run_simulation
from lob_sim.engine import LimitOrderBook, Side
from lob_sim.metrics import (
    book_imbalance,
    imbalance_vs_forward_return,
    microprice,
    signed_order_flow,
)


def test_imbalance_balanced_book_zero():
    b = LimitOrderBook()
    b.add_limit(Side.BID, 99.0, 10)
    b.add_limit(Side.ASK, 101.0, 10)
    assert book_imbalance(b) == pytest.approx(0.0)


def test_imbalance_bid_heavy_positive():
    b = LimitOrderBook()
    b.add_limit(Side.BID, 99.0, 30)
    b.add_limit(Side.ASK, 101.0, 10)
    assert book_imbalance(b) == pytest.approx(0.5)


def test_imbalance_empty_book_none():
    assert book_imbalance(LimitOrderBook()) is None
    assert microprice(LimitOrderBook()) is None


def test_microprice_tilts_toward_thin_side():
    b = LimitOrderBook()
    b.add_limit(Side.BID, 99.0, 30)
    b.add_limit(Side.ASK, 101.0, 10)
    mp = microprice(b)
    # thin ask side -> microprice closer to ask
    assert 100.0 < mp < 101.0


def test_signed_order_flow():
    assert signed_order_flow(["bid", "bid", "ask"]) == 1
    assert signed_order_flow([]) == 0


def test_imbalance_predicts_direction_on_trended_series():
    # rising prices with positive imbalance -> positive gap
    imb = [0.5] * 50 + [-0.5] * 50
    mid = [100 + i * 0.1 for i in range(50)] + [105 - i * 0.1 for i in range(50)]
    out = imbalance_vs_forward_return(imb, mid, horizon=5)
    assert out["n_pos"] > 0 and out["n_neg"] > 0
    assert out["gap"] > 0


def test_simulation_pipeline_deterministic():
    r1 = run_simulation(n_events=200, seed=7)
    r2 = run_simulation(n_events=200, seed=7)
    assert r1["midprices"] == r2["midprices"]
    assert r1["imbalances"] == r2["imbalances"]
    assert len(r1["midprices"]) == 200
