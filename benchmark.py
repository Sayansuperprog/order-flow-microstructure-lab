"""Full-simulation wall-clock benchmark, not exchange execution latency."""

import cProfile
import csv
import gc
import hashlib
import io
import json
import platform
import pstats
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

import numpy as np

from lob_sim.data import run_simulation

OUTPUT = Path(__file__).resolve().parent / "results"
SIZES = (2000, 10000, 50000)
REPEATS = 5
SEED = 42


def fingerprint(result: dict) -> str:
    """Economic outputs; process-global order IDs deliberately excluded."""
    payload = {k: v for k, v in result.items() if k != "book"}
    payload["fills"] = [(t.price, t.quantity, t.aggressor_side.value, t.timestamp)
                        for t in result["book"].trades]
    payload["final_book"] = result["book"].snapshot(levels=100)
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def cpu_name() -> str:
    if platform.system() == "Windows":
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                           r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as key:
            return str(winreg.QueryValueEx(key, "ProcessorNameString")[0]).strip()
    return platform.processor() or "Unknown"


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def plot(summary: list[dict]) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from lob_sim.report_style import REPORT_STYLE, COLORS

    with plt.rc_context(REPORT_STYLE):
        fig, axes = plt.subplots(1, 2, figsize=(12, 5))
        fig.set_facecolor("#f8fafc")
        fig.subplots_adjust(top=0.71, bottom=0.24, left=0.08, right=0.97, wspace=0.30)
        fig.text(0.08, 0.93, "PERFORMANCE / FULL SIMULATION", fontsize=19, weight="bold")
        fig.text(0.08, 0.86, "Snapshot reuse removes a redundant depth scan", fontsize=13, color="#475569")
        fig.text(0.08, 0.80, "Baseline flow | seed 42 | 5 paired repeats | Python perf_counter | lower runtime is better",
                 fontsize=10, color="#64748b")
        x = np.arange(len(SIZES))
        for version, color, offset in [("before", COLORS[0], -0.18), ("after", COLORS[2], 0.18)]:
            rows = [r for r in summary if r["version"] == version]
            median = np.array([r["median_seconds"] for r in rows])
            p95 = np.array([r["p95_seconds"] for r in rows])
            axes[0].bar(x + offset, median, width=0.34, color=color,
                        label=version.title(), zorder=3)
            axes[0].errorbar(x + offset, median, yerr=[np.zeros(3), p95 - median],
                             fmt="none", ecolor="#334155", capsize=4, zorder=4)
            axes[1].plot(x, [r["events_per_second"] for r in rows], "o-", color=color,
                         lw=2, label=version.title())
        for ax in axes:
            ax.set_facecolor("white")
            ax.set_xticks(x, ["2,000", "10,000", "50,000"])
            ax.set_xlabel("Events per full run")
            ax.grid(axis="y", color="#e2e8f0")
            ax.set_axisbelow(True)
        axes[0].set_yscale("log")
        axes[0].set_ylabel("Full-run seconds (log scale)")
        axes[1].set_ylabel("Throughput (events/s)")
        handles, labels = axes[0].get_legend_handles_labels()
        fig.legend(handles, labels, frameon=False, ncol=2, loc="upper right",
                   bbox_to_anchor=(0.97, 0.91))
        axes[1].set_ylim(bottom=0)
        fig.text(0.08, 0.11, "Bars: median runtime; whiskers: p95 (linear percentile, 5 samples). GC enabled; imports and I/O excluded.",
                 fontsize=9, color="#64748b")
        fig.text(0.08, 0.055, "Synthetic workload with snapshots and metrics. These measurements are not order execution latency.",
                 fontsize=9, color="#64748b")
        if any(r["p95_seconds"] > 5 * r["median_seconds"] for r in summary):
            fig.text(0.08, 0.015, "Long reference-run outlier retained in p95; inspect raw measurements and the timing note in README.",
                     fontsize=9, color="#b45309")
        fig.savefig(OUTPUT / "benchmark.png", dpi=180)
        plt.close(fig)


def main() -> None:
    OUTPUT.mkdir(exist_ok=True)
    environment = {
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "python": platform.python_version(), "implementation": platform.python_implementation(),
        "cpu": cpu_name(), "os": platform.platform(), "numpy": np.__version__,
        "events": SIZES, "repeats": REPEATS, "seed": SEED,
        "regime": "Baseline; default flow parameters; L3 snapshots every event",
        "timer": "time.perf_counter", "gc_enabled": gc.isenabled(),
        "warmup": "One untimed 2000-event run per version",
        "ordering": "Paired versions; before/after order alternates by repetition",
        "timed_scope": "run_simulation only, including initialization and all histories; excludes imports, hashing, GC collection, destruction, plotting and I/O",
        "percentile": "numpy.percentile(method='linear'); p95 from only five samples is descriptive",
        "before": "reuse_snapshot_metrics=False: original redundant book_imbalance scan",
        "after": "reuse_snapshot_metrics=True: L3 imbalance from existing snapshot",
    }
    print(json.dumps(environment, indent=2), flush=True)
    for reuse in (False, True):
        run_simulation(2000, SEED, reuse_snapshot_metrics=reuse)
    raw, summary = [], []
    for size in SIZES:
        expected = None
        for repeat in range(1, REPEATS + 1):
            versions = ("before", "after") if repeat % 2 else ("after", "before")
            for version in versions:
                gc.collect()
                start = perf_counter()
                result = run_simulation(size, SEED, reuse_snapshot_metrics=version == "after")
                elapsed = perf_counter() - start
                digest = fingerprint(result)
                if expected is None:
                    expected = digest
                if digest != expected:
                    raise RuntimeError(f"Output mismatch: {size} events, {version}, repeat {repeat}")
                raw.append({"version": version, "events": size, "repeat": repeat,
                            "seed": SEED, "seconds": elapsed, "events_per_second": size / elapsed,
                            "output_sha256": digest})
                del result
                print(f"{size:>6} events | {version:6} | repeat {repeat} | {elapsed:.6f}s", flush=True)
        for version in ("before", "after"):
            times = [r["seconds"] for r in raw if r["events"] == size and r["version"] == version]
            median = float(np.median(times))
            summary.append({"version": version, "events": size, "repeats": REPEATS,
                            "median_seconds": median,
                            "p95_seconds": float(np.percentile(times, 95, method="linear")),
                            "events_per_second": size / median})
    write_csv(OUTPUT / "benchmark_runs.csv", raw)
    write_csv(OUTPUT / "benchmark_summary.csv", summary)
    environment["correctness"] = "All paired economic output SHA-256 digests match at every size and repeat"
    (OUTPUT / "benchmark_environment.json").write_text(json.dumps(environment, indent=2) + "\n", encoding="utf-8")
    profile = cProfile.Profile()
    profile.runcall(run_simulation, 10000, SEED, reuse_snapshot_metrics=False)
    stream = io.StringIO()
    pstats.Stats(profile, stream=stream).strip_dirs().sort_stats("cumulative").print_stats(20)
    (OUTPUT / "benchmark_profile.txt").write_text(stream.getvalue(), encoding="utf-8")
    plot(summary)
    for row in summary:
        print(row, flush=True)


if __name__ == "__main__":
    main()
