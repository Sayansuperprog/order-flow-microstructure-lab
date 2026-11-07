"""Reproduce the synthetic three-regime study: python experiment.py."""

from pathlib import Path
import csv

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from lob_sim.data import run_simulation
from lob_sim.report_style import COLORS, REPORT_STYLE


N_EVENTS = 2000
SEED = 42
BASE_PRICE = 100.0
REGIMES = {
    "Baseline": {},
    "Thin Liquidity": {"liquidity_scale": 0.15},
    "Aggressive Order Flow": {
        "market_probability": 0.25, "market_size_scale": 2.0,
        "market_buy_probability": 0.55,
    },
}
OUTPUT = Path(__file__).resolve().parent / "results"


def summarize(name: str, result: dict) -> tuple[dict, tuple]:
    """Use raw snapshots; never fill missing prices or bridge return gaps."""
    snapshots = result["snapshots"]
    mid = np.array([s["midprice"] for s in snapshots], dtype=float)
    spread = np.array([s["spread"] for s in snapshots], dtype=float)
    depth = np.array([
        [sum(q for _, q in s[side]) for side in ("bids", "asks")]
        for s in snapshots
    ], dtype=float)
    total = depth.sum(axis=1)
    imbalance = np.divide(depth[:, 0] - depth[:, 1], total,
                          out=np.full(len(total), np.nan), where=total > 0)
    # Include event zero, whose seeded best quotes are 99.95 and 100.05.
    prices = np.r_[BASE_PRICE, mid]
    valid_pairs = np.isfinite(prices[:-1]) & np.isfinite(prices[1:])
    returns = (prices[1:][valid_pairs] / prices[:-1][valid_pairs] - 1) * 10_000
    row = {
        "regime": name, "seed": SEED, "events": len(snapshots),
        "liquidity_scale": 1.0, "market_probability": 0.07,
        "market_size_scale": 1.0, "market_buy_probability": 0.5,
        **REGIMES[name],
        "trade_fills": len(result["book"].trades),
        "mean_spread": float(np.nanmean(spread)),
        "midprice_change": float(mid[-1] - BASE_PRICE),
        "volatility_bps_per_event": float(np.std(returns, ddof=1)) if len(returns) > 1 else np.nan,
        "mean_imbalance_l3": float(np.nanmean(imbalance)),
        "two_sided_quote_pct": float(np.isfinite(mid).mean() * 100),
        "valid_return_pairs": int(valid_pairs.sum()),
    }
    return row, (mid, spread, imbalance)


def plot_study(series: dict, rows: list[dict], path: Path) -> None:
    with plt.rc_context(REPORT_STYLE):
        fig, axes = plt.subplots(3, 1, figsize=(12, 10), sharex=True,
                                 gridspec_kw={"height_ratios": [1.5, 1, 1]})
        fig.set_facecolor("#f8fafc")
        fig.subplots_adjust(top=0.82, bottom=0.12, left=0.10, right=0.97, hspace=0.28)
        fig.text(0.10, 0.955, "ORDER FLOW & MARKET MICROSTRUCTURE LAB",
                 fontsize=19, weight="bold")
        fig.text(0.10, 0.92, "Liquidity and aggressive flow reshape the book",
                 fontsize=14, color="#475569")
        fig.text(0.10, 0.89, "Synthetic data  /  2,000 events per regime  /  seed 42  /  common starting midprice 100",
                 fontsize=10, color="#64748b")
        events = np.arange(1, N_EVENTS + 1)
        for (name, values), color in zip(series.items(), COLORS):
            mid, spread, imbalance = values
            axes[0].plot(np.r_[0, events], np.r_[0, mid - BASE_PRICE],
                         color=color, label=name, lw=1.8)
            axes[1].plot(events, spread, color=color, lw=1.0, alpha=0.85)
            # Non-overlapping windows reduce clutter; gaps remain gaps.
            blocks = imbalance.reshape(-1, 50)
            axes[2].plot(np.arange(25.5, N_EVENTS, 50), np.mean(blocks, axis=1),
                         color=color, lw=1.8)
        axes[0].legend(loc="lower left", bbox_to_anchor=(0, 1.02), ncol=3,
                       frameon=False, borderaxespad=0)
        labels = ["Midprice change\n(price units)", "Spread\n(price units)", "L3 imbalance\n(50-event means)"]
        for ax, label in zip(axes, labels):
            ax.set_facecolor("white")
            ax.set_ylabel(label, labelpad=12)
            ax.grid(axis="y", color="#e2e8f0", lw=0.7)
            ax.set_axisbelow(True)
        axes[0].axhline(0, color="#94a3b8", lw=0.7, ls="--")
        axes[2].axhline(0, color="#94a3b8", lw=0.7, ls="--")
        axes[2].set_ylim(-1, 1)
        axes[2].set_xlabel("Event index (event time; no wall-clock calibration)", labelpad=10)
        coverage = " / ".join(f"{r['regime']}: {r['two_sided_quote_pct']:.1f}%" for r in rows)
        fig.text(0.10, 0.055, "Two-sided quote coverage — " + coverage, fontsize=9, color="#64748b")
        fig.text(0.10, 0.03, "Single-seed scenario comparison. No fitted model, exchange data, or profitability claim.",
                 fontsize=9, color="#64748b")
        fig.savefig(path, dpi=180)
        plt.close(fig)


def main() -> None:
    OUTPUT.mkdir(exist_ok=True)
    rows, series = [], {}
    for name, config in REGIMES.items():
        result = run_simulation(n_events=N_EVENTS, seed=SEED, base_price=BASE_PRICE, **config)
        row, values = summarize(name, result)
        rows.append(row)
        series[name] = values
    with (OUTPUT / "regime_summary.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    plot_study(series, rows, OUTPUT / "regime_comparison.png")
    for row in rows:
        print(f"{row['regime']}: fills={row['trade_fills']}, spread={row['mean_spread']:.6f}, "
              f"mid change={row['midprice_change']:+.6f}, "
              f"vol={row['volatility_bps_per_event']:.6f} bp/event, "
              f"imbalance={row['mean_imbalance_l3']:+.6f}, "
              f"quote coverage={row['two_sided_quote_pct']:.2f}%")
    print(f"Artifacts: {OUTPUT}")


if __name__ == "__main__":
    main()
