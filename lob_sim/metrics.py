"""Book imbalance / microstructure metrics + short-horizon move study."""

from __future__ import annotations

from typing import List, Optional, Sequence

from lob_sim.engine import LimitOrderBook, Side


def spread(book: LimitOrderBook) -> Optional[float]:
    return book.spread()


def midprice(book: LimitOrderBook) -> Optional[float]:
    return book.midprice()


def book_imbalance(book: LimitOrderBook, levels: int = 1) -> Optional[float]:
    """(bid_qty - ask_qty) / (bid_qty + ask_qty) over top `levels`. Range [-1, 1]."""
    b = book.total_depth(Side.BID, levels)
    a = book.total_depth(Side.ASK, levels)
    if b + a == 0:
        return None
    return (b - a) / (b + a)


def microprice(book: LimitOrderBook, levels: int = 1) -> Optional[float]:
    """Quantity-weighted price: (ask_qty*bid_px + bid_qty*ask_px)/(bid+ask)."""
    if book.best_bid is None or book.best_ask is None:
        return None
    b = book.total_depth(Side.BID, levels)
    a = book.total_depth(Side.ASK, levels)
    if b + a == 0:
        return None
    return (a * book.best_bid + b * book.best_ask) / (b + a)


def depth_at_levels(book: LimitOrderBook, levels: int = 5) -> dict:
    snap = book.snapshot(levels)
    return {
        "bid_depth": sum(q for _, q in snap["bids"]),
        "ask_depth": sum(q for _, q in snap["asks"]),
    }


def signed_order_flow(trade_sides: Sequence[str]) -> int:
    """Net aggressive flow: +1 per buyer-initiated trade, -1 per seller-initiated."""
    return sum(1 if s == "bid" else -1 for s in trade_sides)


def imbalance_vs_forward_return(
    imbalances: Sequence[float], midprices: Sequence[float], horizon: int = 5
) -> dict:
    """Bucket forward midprice returns by imbalance sign; report group means.

    Returns dict with mean forward return for positive/negative imbalance
    observations and the long-short gap (pos - neg). Positive gap means
    imbalance predicts the direction of the short-term move.
    """
    import numpy as np

    imb = np.asarray(imbalances, dtype=float)
    mid = np.asarray(midprices, dtype=float)
    n = len(mid)
    if n != len(imb):
        raise ValueError("imbalances and midprices must have equal length")
    if n <= horizon:
        raise ValueError("not enough observations for horizon")
    fwd = (mid[horizon:] - mid[:-horizon]) / mid[:-horizon]
    aligned = imb[:-horizon]
    pos = fwd[aligned > 0]
    neg = fwd[aligned < 0]
    out = {
        "n_pos": int(len(pos)),
        "n_neg": int(len(neg)),
        "mean_ret_pos": float(pos.mean()) if len(pos) else float("nan"),
        "mean_ret_neg": float(neg.mean()) if len(neg) else float("nan"),
    }
    out["gap"] = out["mean_ret_pos"] - out["mean_ret_neg"]
    return out


def top_of_book_series(snapshots: List[dict]) -> dict:
    """Collapse snapshot history into column lists for plotting/analysis."""
    return {
        "mid": [s["midprice"] for s in snapshots],
        "spread": [s["spread"] for s in snapshots],
    }
