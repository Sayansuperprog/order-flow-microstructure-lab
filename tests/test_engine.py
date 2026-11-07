"""Synthetic-only engine tests: matching, price-time priority, queue, cancels."""

import pytest

from lob_sim.engine import LimitOrderBook, Side


def seeded_book() -> LimitOrderBook:
    b = LimitOrderBook()
    b.add_limit(Side.BID, 99.5, 10)
    b.add_limit(Side.BID, 99.0, 20)
    b.add_limit(Side.ASK, 100.5, 10)
    b.add_limit(Side.ASK, 101.0, 20)
    return b


def test_best_and_spread():
    b = seeded_book()
    assert b.best_bid == 99.5
    assert b.best_ask == 100.5
    assert b.spread() == pytest.approx(1.0)
    assert b.midprice() == pytest.approx(100.0)


def test_limit_cross_matches_immediately():
    b = seeded_book()
    _, fills = b.add_limit(Side.BID, 100.5, 4)
    assert len(fills) == 1
    assert fills[0].price == pytest.approx(100.5)
    assert fills[0].quantity == 4
    assert b.depth(Side.ASK, 100.5) == 6


def test_price_priority_best_level_first():
    b = LimitOrderBook()
    b.add_limit(Side.ASK, 101.0, 5)
    b.add_limit(Side.ASK, 100.5, 5)
    fills = b.add_market(Side.BID, 7)
    assert fills[0].price == pytest.approx(100.5)
    assert fills[-1].price == pytest.approx(101.0)
    assert sum(f.quantity for f in fills) == 7


def test_time_priority_fifo_within_level():
    b = LimitOrderBook()
    oid1, _ = b.add_limit(Side.ASK, 100.0, 5)
    oid2, _ = b.add_limit(Side.ASK, 100.0, 5)
    fills = b.add_market(Side.BID, 5)
    assert fills[0].maker_order_id == oid1
    assert b.queue_position(oid1) is None  # fully filled
    assert b.queue_position(oid2) is not None


def test_queue_position_counts_ahead_quantity():
    b = LimitOrderBook()
    oid1, _ = b.add_limit(Side.BID, 99.0, 10)
    oid2, _ = b.add_limit(Side.BID, 99.0, 20)
    pos, ahead = b.queue_position(oid2)
    assert pos == 2
    assert ahead == 10
    assert b.queue_position(oid1)[0] == 1


def test_cancel_removes_order():
    b = LimitOrderBook()
    oid, _ = b.add_limit(Side.BID, 99.0, 10)
    assert b.cancel(oid) is True
    assert b.cancel(oid) is False
    assert b.depth(Side.BID, 99.0) == 0


def test_market_sweep_partial_when_book_thin():
    b = LimitOrderBook()
    b.add_limit(Side.ASK, 100.0, 3)
    fills = b.add_market(Side.BID, 10)
    assert sum(f.quantity for f in fills) == 3
    assert b.best_ask is None


def test_non_marketable_limit_rests():
    b = LimitOrderBook()
    oid, fills = b.add_limit(Side.BID, 90.0, 5)
    assert fills == []
    assert b.best_bid == 90.0
    assert b.queue_position(oid)[0] == 1


def test_invalid_quantity_rejected():
    b = LimitOrderBook()
    with pytest.raises(ValueError):
        b.add_limit(Side.BID, 99.0, 0)
    with pytest.raises(ValueError):
        b.add_market(Side.ASK, -1)
