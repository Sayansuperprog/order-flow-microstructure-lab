"""Synthetic order-flow generator (deterministic with seed; no network)."""

from __future__ import annotations

import numpy as np

from lob_sim.engine import LimitOrderBook, Side


def run_simulation(
    n_events: int = 2000, seed: int = 42, base_price: float = 100.0, *,
    liquidity_scale: float = 1.0, market_probability: float = 0.07,
    market_size_scale: float = 1.0, market_buy_probability: float = 0.5,
    reuse_snapshot_metrics: bool = True,
) -> dict:
    """Generate random limit/market/cancel flow against a LimitOrderBook.

    Scale both initial and arriving limit quantities to control liquidity.
    Cancellation probability stays at 3%; remaining non-market flow is split
    equally between limit bids and asks. Defaults preserve the original flow.
    Histories retain legacy fallbacks; snapshots expose missing quotes as None.
    Set reuse_snapshot_metrics=False to benchmark the original metric path.
    """
    if n_events < 1 or not np.isfinite(base_price) or base_price <= 0.5:
        raise ValueError("n_events must be positive and base_price must exceed 0.5")
    if not np.isfinite(liquidity_scale) or liquidity_scale <= 0:
        raise ValueError("liquidity_scale must be finite and positive")
    if not np.isfinite(market_size_scale) or market_size_scale <= 0:
        raise ValueError("market_size_scale must be finite and positive")
    if not 0 <= market_probability <= 0.97 or not 0 <= market_buy_probability <= 1:
        raise ValueError("invalid market probability")
    rng = np.random.default_rng(seed)
    limit_probability = (0.97 - market_probability) / 2

    def limit_quantity(low: int, high: int) -> int:
        return max(1, int(rng.integers(low, high) * liquidity_scale))

    book = LimitOrderBook()
    # seed the book with depth on both sides
    for i in range(10):
        book.add_limit(Side.BID, base_price - 0.05 * (i + 1), limit_quantity(5, 50))
        book.add_limit(Side.ASK, base_price + 0.05 * (i + 1), limit_quantity(5, 50))

    live_ids: list[int] = []
    snapshots, imbalances, mids, spreads = [], [], [], []
    trade_sides: list[str] = []

    from lob_sim.metrics import book_imbalance

    for _ in range(n_events):
        u = rng.random()
        ref = book.midprice() or base_price
        if u < limit_probability:  # limit bid
            px = round(ref - float(rng.integers(1, 10)) * 0.05, 2)
            oid, _ = book.add_limit(Side.BID, px, limit_quantity(1, 30))
            live_ids.append(oid)
        elif u < 2 * limit_probability:  # limit ask
            px = round(ref + float(rng.integers(1, 10)) * 0.05, 2)
            oid, _ = book.add_limit(Side.ASK, px, limit_quantity(1, 30))
            live_ids.append(oid)
        elif u < 0.97:  # market order
            side = Side.BID if rng.random() < market_buy_probability else Side.ASK
            fills = book.add_market(side, max(1, int(rng.integers(1, 20) * market_size_scale)))
            trade_sides.extend([t.aggressor_side.value for t in fills])
        else:  # cancel
            if live_ids:
                oid = live_ids.pop(int(rng.integers(0, len(live_ids))))
                book.cancel(oid)
        snap = book.snapshot(levels=3)
        snapshots.append(snap)
        if reuse_snapshot_metrics:
            bid_qty = sum(q for _, q in snap["bids"])
            ask_qty = sum(q for _, q in snap["asks"])
            total_qty = bid_qty + ask_qty
            imbalance = (bid_qty - ask_qty) / total_qty if total_qty else 0.0
        else:
            imbalance = book_imbalance(book, levels=3) or 0.0
        imbalances.append(imbalance)
        mids.append(book.midprice() or ref)
        spreads.append(book.spread() or 0.0)

    return {
        "book": book,
        "snapshots": snapshots,
        "imbalances": imbalances,
        "midprices": mids,
        "spreads": spreads,
        "trade_sides": trade_sides,
    }
