"""Limit order book simulator: price-time priority matching engine + imbalance metrics."""

from lob_sim.engine import LimitOrderBook, Order, Side, Trade
from lob_sim.metrics import (
    spread,
    midprice,
    book_imbalance,
    microprice,
    depth_at_levels,
    signed_order_flow,
)

__all__ = [
    "LimitOrderBook",
    "Order",
    "Side",
    "Trade",
    "spread",
    "midprice",
    "book_imbalance",
    "microprice",
    "depth_at_levels",
    "signed_order_flow",
]

__version__ = "0.1.0"
