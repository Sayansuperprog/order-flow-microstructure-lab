"""Matplotlib charts for the LOB demo."""

from __future__ import annotations

from typing import Sequence


def plot_book_study(
    midprices: Sequence[float],
    imbalances: Sequence[float],
    spreads: Sequence[float],
    path: str = "lob_study.png",
) -> str:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(3, 1, figsize=(10, 8), sharex=True)
    axes[0].plot(midprices, lw=1)
    axes[0].set_title("Midprice path (synthetic flow)")
    axes[0].set_ylabel("Price")
    axes[1].plot(imbalances, lw=1, color="tab:orange")
    axes[1].axhline(0, color="k", lw=0.8)
    axes[1].set_ylabel("Book imbalance")
    axes[1].set_title("Top-3-level imbalance")
    axes[2].plot(spreads, lw=1, color="tab:green")
    axes[2].set_ylabel("Spread")
    axes[2].set_xlabel("Event")
    axes[2].set_title("Bid-ask spread")
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)
    return path
