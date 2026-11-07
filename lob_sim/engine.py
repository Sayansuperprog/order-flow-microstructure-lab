"""Limit order book engine with price-time priority matching.

Bids sorted descending, asks ascending. Within a price level, FIFO
(time priority). Supports limit orders, market orders, cancels, and
queue-position queries.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from itertools import count
from typing import Deque, Dict, List, Optional

_order_ids = count(1)


class Side(str, Enum):
    BID = "bid"
    ASK = "ask"


@dataclass
class Order:
    side: Side
    price: float
    quantity: int
    timestamp: int = 0
    order_id: int = field(default_factory=lambda: next(_order_ids))

    def __post_init__(self) -> None:
        if self.quantity <= 0:
            raise ValueError("quantity must be positive")
        # inf / 0.0 are internal sentinels for market-order takers
        if self.price not in (float("inf"), 0.0) and self.price <= 0:
            raise ValueError("price must be positive")


@dataclass
class Trade:
    price: float
    quantity: int
    aggressor_side: Side  # side of the incoming order
    maker_order_id: int
    taker_order_id: Optional[int] = None
    timestamp: int = 0


class LimitOrderBook:
    """Price-time priority limit order book."""

    def __init__(self) -> None:
        self.bids: Dict[float, Deque[Order]] = {}
        self.asks: Dict[float, Deque[Order]] = {}
        self._orders: Dict[int, Order] = {}
        self.trades: List[Trade] = []
        self._time = 0

    # -- properties -----------------------------------------------------
    @property
    def best_bid(self) -> Optional[float]:
        return max(self.bids) if self.bids else None

    @property
    def best_ask(self) -> Optional[float]:
        return min(self.asks) if self.asks else None

    def midprice(self) -> Optional[float]:
        if self.best_bid is None or self.best_ask is None:
            return None
        return (self.best_bid + self.best_ask) / 2.0

    def spread(self) -> Optional[float]:
        if self.best_bid is None or self.best_ask is None:
            return None
        return self.best_ask - self.best_bid

    def depth(self, side: Side, price: float) -> int:
        book = self.bids if side == Side.BID else self.asks
        return sum(o.quantity for o in book.get(price, []))

    def total_depth(self, side: Side, levels: int = 5) -> int:
        book = self.bids if side == Side.BID else self.asks
        prices = sorted(book, reverse=(side == Side.BID))[:levels]
        return sum(self.depth(side, p) for p in prices)

    def snapshot(self, levels: int = 5) -> dict:
        bids = sorted(self.bids, reverse=True)[:levels]
        asks = sorted(self.asks)[:levels]
        return {
            "bids": [(p, self.depth(Side.BID, p)) for p in bids],
            "asks": [(p, self.depth(Side.ASK, p)) for p in asks],
            "best_bid": self.best_bid,
            "best_ask": self.best_ask,
            "midprice": self.midprice(),
            "spread": self.spread(),
        }

    # -- order ops ------------------------------------------------------
    def add_limit(self, side: Side, price: float, quantity: int) -> tuple[int, List[Trade]]:
        """Submit a limit order; crosses the spread immediately if marketable."""
        if price <= 0:
            raise ValueError("price must be positive")
        self._time += 1
        order = Order(side=side, price=price, quantity=quantity, timestamp=self._time)
        fills = self._match(order)
        if order.quantity > 0:
            book = self.bids if side == Side.BID else self.asks
            book.setdefault(price, deque()).append(order)
            self._orders[order.order_id] = order
        return order.order_id, fills

    def add_market(self, side: Side, quantity: int) -> List[Trade]:
        """Market order: consume opposite side until filled or book empty."""
        if quantity <= 0:
            raise ValueError("quantity must be positive")
        self._time += 1
        taker = Order(side=side, price=float("inf") if side == Side.BID else 0.0,
                      quantity=quantity, timestamp=self._time)
        return self._match(taker)

    def cancel(self, order_id: int) -> bool:
        order = self._orders.pop(order_id, None)
        if order is None:
            return False
        book = self.bids if order.side == Side.BID else self.asks
        level = book.get(order.price)
        if level is None:
            return False
        for i, o in enumerate(level):
            if o.order_id == order_id:
                del level[i]
                break
        if not level:
            book.pop(order.price, None)
        return True

    def queue_position(self, order_id: int) -> Optional[tuple[int, int]]:
        """Return (position_in_level, level_size) with 1 = front of queue."""
        order = self._orders.get(order_id)
        if order is None:
            return None
        book = self.bids if order.side == Side.BID else self.asks
        level = book.get(order.price, deque())
        for i, o in enumerate(level):
            if o.order_id == order_id:
                ahead_qty = sum(x.quantity for x in list(level)[:i])
                return (i + 1, ahead_qty)
        return None

    # -- matching -------------------------------------------------------
    def _match(self, taker: Order) -> List[Trade]:
        fills: List[Trade] = []
        opposite = self.asks if taker.side == Side.BID else self.bids
        while taker.quantity > 0 and opposite:
            if taker.side == Side.BID:
                best = min(opposite)
                if taker.price != float("inf") and taker.price < best:
                    break
            else:
                best = max(opposite)
                if taker.price != 0.0 and taker.price > best:
                    break
            level = opposite[best]
            while taker.quantity > 0 and level:
                maker = level[0]
                fill_qty = min(taker.quantity, maker.quantity)
                taker.quantity -= fill_qty
                maker.quantity -= fill_qty
                fills.append(Trade(price=best, quantity=fill_qty,
                                   aggressor_side=taker.side,
                                   maker_order_id=maker.order_id,
                                   taker_order_id=taker.order_id,
                                   timestamp=self._time))
                if maker.quantity == 0:
                    level.popleft()
                    self._orders.pop(maker.order_id, None)
            if not level:
                opposite.pop(best, None)
        self.trades.extend(fills)
        return fills
