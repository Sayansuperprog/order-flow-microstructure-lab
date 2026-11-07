"""CLI demo: simulate synthetic flow, print spread/depth/imbalance study."""

from __future__ import annotations

import argparse

from lob_sim.data import run_simulation
from lob_sim.engine import Side
from lob_sim.metrics import book_imbalance, imbalance_vs_forward_return, microprice
from lob_sim.viz import plot_book_study


def main() -> None:
    ap = argparse.ArgumentParser(description="Limit order book simulator demo")
    ap.add_argument("--n-events", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--levels", type=int, default=3)
    ap.add_argument("--horizon", type=int, default=10)
    ap.add_argument("--plot", type=str, default="lob_study.png")
    args = ap.parse_args()

    res = run_simulation(n_events=args.n_events, seed=args.seed)
    book = res["book"]
    study = imbalance_vs_forward_return(res["imbalances"], res["midprices"], horizon=args.horizon)
    imb_now = book_imbalance(book, levels=args.levels)
    mp = microprice(book, levels=args.levels)
    snap = book.snapshot(levels=args.levels)
    bid_depth = sum(q for _, q in snap["bids"])
    ask_depth = sum(q for _, q in snap["asks"])
    path = plot_book_study(res["midprices"], res["imbalances"], res["spreads"], path=args.plot)

    print(f"events={args.n_events} seed={args.seed} trades={len(book.trades)}")
    print(f"best_bid={snap['best_bid']} best_ask={snap['best_ask']} "
          f"spread={snap['spread']:.4f} mid={snap['midprice']:.4f}")
    print(f"depth L{args.levels}: bid={bid_depth} ask={ask_depth}")
    print(f"imbalance(L{args.levels})={imb_now:+.3f} microprice={mp:.4f}")
    print(f"forward(h={args.horizon}): n_pos={study['n_pos']} n_neg={study['n_neg']} "
          f"mean_ret_pos={study['mean_ret_pos']:+.6f} "
          f"mean_ret_neg={study['mean_ret_neg']:+.6f} gap={study['gap']:+.6f}")
    print(f"chart -> {path}")


if __name__ == "__main__":
    main()
