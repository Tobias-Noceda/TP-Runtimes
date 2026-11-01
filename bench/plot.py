# Summarises a run_bench.sh results directory: summary.csv plus one figure per
# (board, algorithm) with mean time ± std and speedup over one worker.
# Runs on CPython with matplotlib (run_bench.sh calls it through uv), never on
# protopy.
#
# Usage: plot.py <results dir>

import csv
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

RUNTIME_ORDER = ["cpython", "cpython-ft-gil", "cpython-ft", "protopy"]
LABELS = {
    "cpython": "CPython 3.14 (GIL)",
    "cpython-ft-gil": "CPython 3.14t, PYTHON_GIL=1",
    "cpython-ft": "CPython 3.14t (free-threaded)",
    "protopy": "protoPython (GIL-free)",
}
COLORS = {
    "cpython": "#4C72B0",
    "cpython-ft-gil": "#8172B3",
    "cpython-ft": "#55A868",
    "protopy": "#DD8452",
}


def load(results_dir: Path) -> list[dict]:
    samples = []
    with open(results_dir / "results.jsonl") as f:
        for line in f:
            line = line.strip()
            if line:
                samples.append(json.loads(line))
    return samples


def summarise(samples: list[dict]) -> list[dict]:
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for s in samples:
        groups[(s["board"], s["algorithm"], s["heuristic"], s["runtime"], s["workers"])].append(s)

    rows = []
    for (board, algorithm, heuristic, runtime, workers), group in sorted(groups.items()):
        times = [s["seconds"] for s in group if s["status"] == "ok"]
        steps = sorted({s["steps"] for s in group if s["status"] == "ok" and s.get("steps") is not None})
        rows.append({
            "board": board,
            "algorithm": algorithm,
            "heuristic": heuristic,
            "runtime": runtime,
            "workers": workers,
            "runs": len(group),
            "ok": len(times),
            "timeouts": sum(s["status"] == "timeout" for s in group),
            "errors": sum(s["status"] == "error" for s in group),
            "mean_s": statistics.fmean(times) if times else None,
            "std_s": statistics.stdev(times) if len(times) > 1 else 0.0 if times else None,
            "min_s": min(times) if times else None,
            "max_s": max(times) if times else None,
            "steps": "/".join(map(str, steps)),
        })
    return rows


def write_csv(rows: list[dict], path: Path) -> None:
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def runtimes_in(rows: list[dict]) -> list[str]:
    present = {r["runtime"] for r in rows}
    return [rt for rt in RUNTIME_ORDER if rt in present] + sorted(present - set(RUNTIME_ORDER))


def plot_board(rows: list[dict], title: str, path: Path) -> None:
    runtimes = runtimes_in(rows)
    workers = sorted({r["workers"] for r in rows})
    parallel = len(workers) > 1

    fig, axes = plt.subplots(1, 2 if parallel else 1, figsize=(12 if parallel else 7, 4.8), squeeze=False)
    ax_time = axes[0][0]

    for i, rt in enumerate(runtimes):
        by_w = {r["workers"]: r for r in rows if r["runtime"] == rt and r["mean_s"] is not None}
        if not by_w:
            continue
        ws = [w for w in workers if w in by_w]
        means = [by_w[w]["mean_s"] for w in ws]
        stds = [by_w[w]["std_s"] for w in ws]
        color = COLORS.get(rt)

        if parallel:
            ax_time.errorbar(ws, means, yerr=stds, label=LABELS.get(rt, rt), color=color,
                             marker="o", capsize=4, linewidth=2)
            base = by_w.get(workers[0])
            if base:
                speedups = [base["mean_s"] / m for m in means]
                # Error of a ratio of two means, first order.
                errs = [s * base["mean_s"] / (m * m) for s, m in zip(stds, means)]
                axes[0][1].errorbar(ws, speedups, yerr=errs, label=LABELS.get(rt, rt), color=color,
                                    marker="o", capsize=4, linewidth=2)
        else:
            ax_time.bar(i, means[0], yerr=stds[0], color=color, capsize=6, label=LABELS.get(rt, rt))

    for r in rows:
        if r["timeouts"] or r["errors"]:
            note = f"{r['runtime']} w={r['workers']}: {r['timeouts']} timeout(s), {r['errors']} error(s)"
            ax_time.annotate(note, xy=(0.01, 0.01), xycoords="axes fraction", fontsize=7, color="crimson")

    ax_time.set_yscale("log")
    ax_time.set_ylabel("solver time (s, log scale) — mean ± std")
    ax_time.grid(True, which="both", alpha=0.3)
    if parallel:
        ax_time.set_xlabel("worker threads")
        ax_time.set_xticks(workers)
        ax_time.set_title("Time")
        ax_s = axes[0][1]
        ax_s.plot(workers, [w / workers[0] for w in workers], "k--", alpha=0.4, label="ideal")
        ax_s.set_xlabel("worker threads")
        ax_s.set_ylabel(f"speedup over {workers[0]} worker(s)")
        ax_s.set_xticks(workers)
        ax_s.set_title("Speedup (same runtime)")
        ax_s.grid(True, alpha=0.3)
        ax_s.legend(fontsize=8)
    else:
        ax_time.set_xticks(range(len(runtimes)))
        ax_time.set_xticklabels([LABELS.get(rt, rt) for rt in runtimes], rotation=15, fontsize=8)
    ax_time.legend(fontsize=8)

    fig.suptitle(title)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def main() -> None:
    results_dir = Path(sys.argv[1])
    rows = summarise(load(results_dir))
    if not rows:
        raise SystemExit("no samples")
    write_csv(rows, results_dir / "summary.csv")

    by_plot: dict[tuple, list[dict]] = defaultdict(list)
    for r in rows:
        by_plot[(r["board"], r["algorithm"], r["heuristic"])].append(r)

    for (board, algorithm, heuristic), group in by_plot.items():
        runs = max(r["runs"] for r in group)
        title = f"{board} — {algorithm} ({heuristic}), {runs} runs per point"
        plot_board(group, title, results_dir / f"{board}_{algorithm}_{heuristic}.png")

    print(f"{'board':10} {'runtime':15} {'w':>2} {'mean s':>9} {'std s':>8} {'ok':>4}  steps")
    for r in rows:
        mean = f"{r['mean_s']:.3f}" if r["mean_s"] is not None else "-"
        std = f"{r['std_s']:.3f}" if r["std_s"] is not None else "-"
        print(f"{r['board']:10} {r['runtime']:15} {r['workers']:>2} {mean:>9} {std:>8} {r['ok']:>2}/{r['runs']}  {r['steps']}")
    print(f"\nsummary.csv and plots in {results_dir}")


if __name__ == "__main__":
    main()
