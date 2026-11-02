# Builds every chart for the presentation from the night run results.
#
# Usage (from the repo root, system CPython with matplotlib):
#   python3 presentation/make_figures.py [night results dir]
#
# Writes presentation/figures/*.png (+ .svg) and presentation/data/*.csv.
# Reads only files under bench/results/<night>/ and res/boards/, so it can be
# re-run at any time without touching the runtimes.

import csv
import json
import re
import statistics
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle

ROOT = Path(__file__).resolve().parent.parent
NIGHT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "bench/results/night-20261102-0108"
OUT = ROOT / "presentation/figures"
DATA = ROOT / "presentation/data"
OUT.mkdir(parents=True, exist_ok=True)
DATA.mkdir(parents=True, exist_ok=True)

RT = ["cpython", "cpython-ft-gil", "cpython-ft", "protopy"]
LABEL = {
    "cpython": "CPython 3.14 (GIL)",
    "cpython-ft-gil": "CPython 3.14t, GIL on",
    "cpython-ft": "CPython 3.14t, free-threaded",
    "protopy": "protoPython (no GIL)",
}
SHORT = {"cpython": "CPython", "cpython-ft-gil": "3.14t + GIL", "cpython-ft": "3.14t no GIL", "protopy": "protoPython"}
COLOR = {"cpython": "#4C72B0", "cpython-ft-gil": "#8172B3", "cpython-ft": "#55A868", "protopy": "#DD8452"}
INK = "#222222"
MUTED = "#777777"
GOOD = "#2E8B57"
BAD = "#C0392B"
BOARDS = ["soko_01", "microban", "Patrick/P110"]
BOARD_TITLE = {"soko_01": "soko_01", "microban": "microban", "Patrick/P110": "P110"}

plt.rcParams.update({
    "font.size": 14,
    "axes.titlesize": 16,
    "axes.titleweight": "bold",
    "axes.labelsize": 14,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.edgecolor": "#888888",
    "axes.grid": True,
    "grid.alpha": 0.25,
    "legend.frameon": False,
    "legend.fontsize": 12,
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "savefig.facecolor": "white",
    "text.color": INK,
    "axes.labelcolor": INK,
    "xtick.color": INK,
    "ytick.color": INK,
})

WIDE = (13.33, 7.5)   # 16:9 full slide
HALF = (8, 6.5)       # half slide / two-column


def save(fig, name):
    fig.savefig(OUT / f"{name}.png", dpi=200, bbox_inches="tight")
    fig.savefig(OUT / f"{name}.svg", bbox_inches="tight")
    plt.close(fig)
    print("figure", name)


def write_csv(name, rows):
    if not rows:
        return
    with open(DATA / f"{name}.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print("data  ", name)


def load(path):
    with open(path) as f:
        return [json.loads(l) for l in f if l.strip()]


def aggregate(samples):
    """(board, runtime, locks, workers) -> stats over status == ok samples."""
    groups = defaultdict(list)
    for s in samples:
        if s.get("status") == "ok":
            groups[(s["board"], s["runtime"], int(s.get("locks", 0)), s["workers"])].append(s)
    out = {}
    for k, g in groups.items():
        t = [s["seconds"] for s in g]
        out[k] = {
            "n": len(g),
            "mean": statistics.fmean(t),
            "std": statistics.stdev(t) if len(t) > 1 else 0.0,
            "expanded": statistics.fmean(s["expanded"] for s in g),
            "regressions": statistics.fmean(s.get("regressions") or 0 for s in g),
            "steps": sorted({s["steps"] for s in g if s.get("steps") is not None}),
            "solved": sum(bool(s.get("solved")) for s in g),
        }
    return out


final = {}
final.update(aggregate(load(NIGHT / "final_reduction/results.jsonl")))
final.update(aggregate(load(NIGHT / "final_p110_trivial/results.jsonl")))
extra = aggregate(load(NIGHT / "extra_workers/results.jsonl"))
over = aggregate(load(NIGHT / "oversubscribed/results.jsonl"))
WORKERS = [1, 2, 4, 6, 8]


def series(table, board, rt, locks, workers=None):
    ws = sorted(w for (b, r, l, w) in table if b == board and r == rt and l == locks)
    if workers:
        ws = [w for w in ws if w in workers]
    return ws, [table[(board, rt, locks, w)] for w in ws]


# ---------------------------------------------------------------- tables
rows = []
for (b, r, l, w), v in sorted(final.items()):
    base = final.get((b, r, l, 1))
    sp = base["mean"] / v["mean"] if base else None
    rows.append({
        "board": b, "runtime": r, "locks": l, "workers": w, "runs": v["n"],
        "mean_s": round(v["mean"], 4), "std_s": round(v["std"], 4),
        "speedup_vs_1w": round(sp, 3) if sp else "",
        "serial_fraction": round((w / sp - 1) / (w - 1), 3) if sp and w > 1 else "",
        "expanded": round(v["expanded"]), "regressions": round(v["regressions"], 1),
        "us_per_node": round(v["mean"] / v["expanded"] * 1e6, 1),
        "steps": "/".join(map(str, v["steps"])),
    })
write_csv("scaling_all_runtimes", rows)

# ---------------------------------------------------------------- 01 boards
def draw_board(ax, path, title):
    b = json.loads(Path(path).read_text())
    X, Y = b["x"], b["y"]
    walls = {tuple(c) for c in b["walls"]}
    wins = {tuple(c) for c in b["wins"]}
    cubes = {tuple(c) for c in b["cubes"]}
    for x in range(X):
        for y in range(Y):
            if (x, y) in walls:
                ax.add_patch(Rectangle((x, y), 1, 1, color="#3B3B3B"))
            else:
                ax.add_patch(Rectangle((x, y), 1, 1, color="#F3EFE6", ec="#E2DCCF", lw=0.5))
    for (x, y) in wins:
        ax.add_patch(plt.Circle((x + .5, y + .5), .18, color="#E74C3C", alpha=.85))
    for (x, y) in cubes:
        on = (x, y) in wins
        ax.add_patch(FancyBboxPatch((x + .14, y + .14), .72, .72, boxstyle="round,pad=0,rounding_size=.12",
                                    color="#2E8B57" if on else "#C68A3E", ec="#6B4A1E", lw=1))
    px, py = b["player"]
    ax.add_patch(plt.Circle((px + .5, py + .5), .32, color="#2C6FBB"))
    ax.set_xlim(0, X)
    ax.set_ylim(Y, 0)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title(title, fontsize=13)
    return b


fig, axes = plt.subplots(1, 3, figsize=(13.33, 5.6), gridspec_kw={"width_ratios": [13, 8, 7], "wspace": .12})
board_info = []
for ax, (name, path, steps) in zip(axes, [
        ("soko_01", ROOT / "res/boards/soko_01.json", 78),
        ("microban", ROOT / "res/boards/microban.json", 63),
        ("P110", ROOT / "res/boards/Patrick/P110.json", 51)]):
    b = json.loads(Path(path).read_text())
    title = f"{name}\n{b['x']}×{b['y']} · {len(b['cubes'])} boxes\noptimal: {steps} moves"
    draw_board(ax, path, title)
    board_info.append({"board": name, "width": b["x"], "height": b["y"], "boxes": len(b["cubes"]), "optimal_moves": steps})
fig.legend(handles=[
    plt.Line2D([], [], marker="o", ls="", color="#2C6FBB", ms=12, label="player"),
    plt.Line2D([], [], marker="s", ls="", color="#C68A3E", ms=12, label="box"),
    plt.Line2D([], [], marker="o", ls="", color="#E74C3C", ms=9, label="goal"),
    plt.Line2D([], [], marker="s", ls="", color="#3B3B3B", ms=12, label="wall"),
], loc="lower center", ncol=4, bbox_to_anchor=(.5, .02))
save(fig, "01_benchmark_boards")
write_csv("boards", board_info)

# ---------------------------------------------------------------- 02 hash collision example
fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
for ax, (player, boxes, label) in zip(axes, [
        ((0, 0), [(0, 1), (0, 2)], "((0,0), ((0,1),(0,2)))"),
        ((0, 1), [(0, 0), (0, 2)], "((0,1), ((0,0),(0,2)))")]):
    # coords are (x, y); draw a 1x3 column.
    for y in range(3):
        ax.add_patch(Rectangle((0, y), 1, 1, color="#F3EFE6", ec="#BBB", lw=1.5))
    for (x, y) in boxes:
        ax.add_patch(FancyBboxPatch((x + .15, y + .15), .7, .7, boxstyle="round,pad=0,rounding_size=.1",
                                    color="#C68A3E", ec="#6B4A1E"))
    ax.add_patch(plt.Circle((player[0] + .5, player[1] + .5), .3, color="#2C6FBB"))
    ax.set_xlim(-2.5, 3.5)
    ax.set_ylim(3.2, -0.4)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.text(.5, 3.6, label, ha="center", va="top", family="monospace", fontsize=13)
fig.text(.5, .93, "Two different states, one hash (old protoPython)", ha="center", fontsize=17, weight="bold")
fig.text(.5, .5, "hash(a) == hash(b)", ha="center", va="center", fontsize=16, color=BAD, weight="bold",
         bbox=dict(boxstyle="round", fc="#FDEDEC", ec=BAD))
fig.text(.5, .02, "old tuple hash  h = h·1000003 ^ hash(item)  cancels across nesting levels → swapped "
         "player/box coordinates collide,\nand protoCore treated equal tuple hashes as equal keys → the set "
         "silently merges distinct states", ha="center", fontsize=11.5, color=MUTED)
save(fig, "02_hash_collision_example")

# ---------------------------------------------------------------- 03 states lost by hash bug
coll = {}
section = None
for line in (NIGHT / "block_7_hash_fix.log").read_text().splitlines():
    m = re.match(r"## (\w+): hash collisions", line)
    if m:
        section = m[1]
        continue
    if line.startswith("##"):
        section = None
    elif section and line.startswith("{"):
        d = json.loads(line)
        coll.setdefault(section, []).append(d)
grids = ["6×6 grid", "8×8 grid"]
fig, ax = plt.subplots(figsize=HALF)
labels = [("old", "protoPython (old hash)", BAD), ("fixed", "protoPython (xxHash fix)", GOOD), ("cpython", "CPython 3.14", COLOR["cpython"])]
width = .26
coll_rows = []
for i, (key, lab, col) in enumerate(labels):
    pct = [100 * d["states_lost_by_set"] / d["states"] for d in coll[key]]
    xs = [g + (i - 1) * width for g in range(len(grids))]
    bars = ax.bar(xs, pct, width, color=col, label=lab)
    for x, p, d in zip(xs, pct, coll[key]):
        ax.text(x, p + .8, f"{p:.1f}%\n({d['states_lost_by_set']:,} of {d['states']:,})" if p else "0",
                ha="center", va="bottom", fontsize=10)
        coll_rows.append({"runtime": lab, "states": d["states"], "distinct_hashes": d["distinct_hashes"],
                          "lost_by_set": d["states_lost_by_set"], "lost_pct": round(p, 2)})
ax.set_xticks(range(len(grids)))
ax.set_xticklabels(["all states, 6×6 grid\n(player + 2 boxes)", "all states, 8×8 grid\n(player + 2 boxes)"])
ax.set_ylabel("distinct states lost by set() (%)")
# Headroom above the tallest bar label (~40 %) so the legend sits in the
# top-right corner without covering it.
ax.set_ylim(0, 55)
ax.set_yticks(range(0, 50, 5))
ax.set_title("A third of the search space vanished")
ax.legend(loc="upper right")
ax.grid(axis="x", visible=False)
save(fig, "03_hash_bug_states_lost")
write_csv("hash_collisions", coll_rows)

# ---------------------------------------------------------------- 04 hash fix: soko_01 result
old = aggregate(load(NIGHT / "hash_fix/tp1_old/results.jsonl"))
new = aggregate(load(NIGHT / "hash_fix/tp1_fixed/results.jsonl"))
fig, axes = plt.subplots(1, 2, figsize=WIDE, gridspec_kw={"width_ratios": [1, 1]})
hf_rows = []
for ax, w in zip(axes, [1, 4]):
    o, n = old[("soko_01", "protopy", 0, w)], new[("soko_01", "protopy", 0, w)]
    ax.bar([0, 1], [o["expanded"], n["expanded"]], color=[BAD, GOOD], width=.55)
    ax.text(0, o["expanded"] * 1.03, f"NO SOLUTION\n{o['expanded']:,.0f} nodes, {o['mean']:.1f} s\n({o['solved']}/{o['n']} runs solved)",
            ha="center", va="bottom", fontsize=12, color=BAD, weight="bold")
    ax.text(1, n["expanded"] * 1.03, f"78-move solution\n{n['expanded']:,.0f} nodes, {n['mean']:.1f} s\n({n['solved']}/{n['n']} runs solved)",
            ha="center", va="bottom", fontsize=12, color=GOOD, weight="bold")
    ax.set_xticks([0, 1])
    ax.set_xticklabels(["old protoPython\n(9cee94c3)", "fixed protoPython\n(xxHash, 4acd5b49)"])
    ax.set_ylim(0, 42000)
    ax.set_ylabel("nodes expanded")
    ax.set_title(f"soko_01, A*, {w} worker{'s' if w > 1 else ''}")
    ax.grid(axis="x", visible=False)
    for tag, v in (("old", o), ("fixed", n)):
        hf_rows.append({"build": tag, "workers": w, "runs": v["n"], "solved": v["solved"], "expanded": round(v["expanded"]),
                        "mean_s": round(v["mean"], 2)})
fig.suptitle("Old hash: the solver \"proves\" a solvable board unsolvable — and the harness logged it as ok",
             fontsize=15, weight="bold")
save(fig, "04_hash_bug_soko01_unsolvable")
write_csv("hash_fix_soko01", hf_rows)

# ---------------------------------------------------------------- 05 lost updates microbench
lw = defaultdict(lambda: defaultdict(list))
lw_distinct = defaultdict(int)
cur = None
for line in (NIGHT / "correctness/lostwrites.txt").read_text().splitlines():
    m = re.match(r"## (\S+) threads=(\d+)", line)
    if m:
        cur = (m[1], int(m[2]))
        continue
    m = re.search(r"dict \d+/\d+ lost (\d+) \| set \d+/\d+ lost (\d+) \| list \d+/\d+ lost (\d+)", line)
    if m and cur:
        lw_distinct[cur[0]] += sum(map(int, m.groups()))
    m = re.search(r"d\[k\] \+= 1\s+\d+/\d+ lost \d+ \(([\d.]+)%", line)
    if m and cur:
        lw[cur[0]][cur[1]].append(float(m[1]))
fig, ax = plt.subplots(figsize=HALF)
lw_rows = []
# cpython-ft-gil is omitted: in this night run night.sh launched it with -I,
# which ignores PYTHON_GIL, so it actually ran free-threaded (fixed since).
for rt in ["cpython", "cpython-ft", "protopy"]:
    ts = sorted(lw[rt])
    means = [statistics.fmean(lw[rt][t]) for t in ts]
    ax.plot(ts, means, marker="o", lw=2.5, ms=8, color=COLOR[rt], label=LABEL[rt])
    for t, m in zip(ts, means):
        lw_rows.append({"runtime": rt, "threads": t, "incr_lost_pct_mean": round(m, 1), "reps": len(lw[rt][t])})
ax.set_xscale("log", base=2)
ax.set_xticks([2, 4, 8, 16])
ax.set_xticklabels(["2", "4", "8", "16"])
ax.set_xlabel("threads")
ax.set_ylabel("updates lost by  d[k] += 1  (%)")
ax.set_ylim(-3, 100)
ax.set_title("Check-then-act loses updates without a GIL")
ax.legend(loc="center right")
tot = sum(lw_distinct[r] for r in ["cpython", "cpython-ft", "protopy"])
ax.text(.02, .97, f"each thread adding its OWN keys to dict / set / list:\n{tot} lost across every runtime and run "
        "→ single operations are atomic", transform=ax.transAxes, va="top", fontsize=10.5, color=MUTED)
save(fig, "05_lost_updates_microbench")
write_csv("lost_updates", lw_rows)

# ---------------------------------------------------------------- 06 A* lost updates (regressions)
fig, axes = plt.subplots(1, 3, figsize=WIDE, sharey=False)
reg_rows = []
for ax, board in zip(axes, BOARDS):
    for rt in RT:
        ws, vs = series(final, board, rt, 0)
        ax.plot(ws, [v["regressions"] for v in vs], marker="o", lw=2.5, color=COLOR[rt], label=LABEL[rt])
        _, vl = series(final, board, rt, 1)
        for w, v, v1 in zip(ws, vs, vl):
            reg_rows.append({"board": board, "runtime": rt, "workers": w, "regressions_no_locks": round(v["regressions"], 1),
                             "regressions_striped_locks": round(v1["regressions"], 1)})
    ax.set_title(BOARD_TITLE[board])
    ax.set_xticks(WORKERS)
    ax.set_xlabel("worker threads")
axes[0].set_ylabel("lost g-score updates per solve")
axes[0].legend(loc="upper left", fontsize=11)
fig.suptitle("Parallel A* without locks: lost updates per solve (mean of 10 runs).  With striped locks: 0 everywhere",
             fontsize=15, weight="bold")
save(fig, "06_astar_lost_updates")
write_csv("astar_lost_updates", reg_rows)

# ---------------------------------------------------------------- 07 wasted work
fig, axes = plt.subplots(1, 3, figsize=WIDE, sharey=True)
for ax, board in zip(axes, BOARDS):
    base = final[(board, "cpython", 1, 1)]["expanded"]
    for rt in ["cpython", "cpython-ft", "protopy"]:
        for locks, ls in ((0, "-"), (1, ":")):
            ws, vs = series(final, board, rt, locks)
            ax.plot(ws, [100 * (v["expanded"] / base - 1) for v in vs], ls=ls, marker="o", lw=2.3, color=COLOR[rt],
                    label=f"{SHORT[rt]}, {'no locks' if locks == 0 else 'striped locks'}")
    ax.set_title(BOARD_TITLE[board])
    ax.set_xticks(WORKERS)
    ax.set_xlabel("worker threads")
axes[0].set_ylabel("extra nodes expanded vs sequential (%)")
axes[0].legend(fontsize=10, loc="upper left")
fig.suptitle("Lost updates turn into wasted work: nodes re-expanded because a better g-score was overwritten",
             fontsize=15, weight="bold")
save(fig, "07_astar_wasted_work")

# ---------------------------------------------------------------- 08 time vs workers
def time_panel(ax, board, locks):
    for rt in RT:
        ws, vs = series(final, board, rt, locks)
        ax.errorbar(ws, [v["mean"] for v in vs], yerr=[v["std"] for v in vs], marker="o", lw=2.5, capsize=4,
                    color=COLOR[rt], label=LABEL[rt])
    ax.set_yscale("log")
    ax.set_title(BOARD_TITLE[board])
    ax.set_xticks(WORKERS)
    ax.set_xlabel("worker threads")


fig, axes = plt.subplots(1, 3, figsize=WIDE)
for ax, board in zip(axes, BOARDS):
    time_panel(ax, board, 1)
axes[0].set_ylabel("solve time (s, log) — mean ± std, 10 runs")
axes[0].legend(fontsize=11, loc="center right")
fig.suptitle("Solve time vs worker threads (A*, striped locks)", fontsize=16, weight="bold")
save(fig, "08_time_vs_workers")

# ---------------------------------------------------------------- 09 speedup
def speedup_panel(ax, board, locks, with_extra=True):
    ax.plot([1, 8], [1, 8], "--", color="#AAAAAA", lw=1.5, label="ideal (linear)")
    for rt in RT:
        base = final[(board, rt, locks, 1)]["mean"]
        pts = {w: v for w, v in zip(*series(final, board, rt, locks))}
        if with_extra and rt == "protopy":
            pts.update({w: v for w, v in zip(*series(extra, board, rt, locks))})
        ws = sorted(pts)
        sp = [base / pts[w]["mean"] for w in ws]
        err = [pts[w]["std"] * base / pts[w]["mean"] ** 2 for w in ws]
        ax.errorbar(ws, sp, yerr=err, marker="o", lw=2.5, capsize=3, color=COLOR[rt], label=LABEL[rt])
    ax.axhline(1, color="#555555", lw=1)
    ax.set_title(BOARD_TITLE[board])
    ax.set_xticks(range(1, 9))
    ax.set_xlabel("worker threads")
    ax.set_ylim(0, 4.2)


fig, axes = plt.subplots(1, 3, figsize=WIDE, sharey=True)
for ax, board in zip(axes, BOARDS):
    speedup_panel(ax, board, 1, with_extra=board != "Patrick/P110")
axes[0].set_ylabel("speedup over 1 worker (same runtime)")
axes[0].legend(fontsize=11, loc="upper left")
fig.suptitle("Only the GIL-free runtime gets faster with threads — and it plateaus at ~2.5×", fontsize=16, weight="bold")
save(fig, "09_speedup_vs_workers")

# ---------------------------------------------------------------- 10 headline: best time per runtime
fig, ax = plt.subplots(figsize=WIDE)
width = .2
head_rows = []
for i, rt in enumerate(RT):
    xs, ys, labs = [], [], []
    for j, board in enumerate(BOARDS):
        ws, vs = series(final, board, rt, 1)
        seq = vs[0]["mean"]
        best_i = min(range(len(vs)), key=lambda k: vs[k]["mean"])
        best = vs[best_i]["mean"]
        xs.append(j + (i - 1.5) * width)
        ys.append(best)
        labs.append(f"{best:.2f}s\n(w={ws[best_i]})" if best < 10 else f"{best:.0f}s\n(w={ws[best_i]})")
        head_rows.append({"board": board, "runtime": rt, "sequential_s": round(seq, 3), "best_s": round(best, 3),
                          "best_workers": ws[best_i], "speedup": round(seq / best, 2),
                          "best_vs_cpython_sequential": round(best / final[(board, "cpython", 1, 1)]["mean"], 1)})
    ax.bar(xs, ys, width, color=COLOR[rt], label=LABEL[rt])
    for x, y, l in zip(xs, ys, labs):
        ax.text(x, y * 1.12, l, ha="center", va="bottom", fontsize=9.5)
ax.set_yscale("log")
ax.set_ylim(0.08, 300)
ax.set_xticks(range(3))
ax.set_xticklabels([BOARD_TITLE[b] for b in BOARDS])
ax.set_ylabel("best solve time over 1–8 workers (s, log)")
ax.set_title("Scaling is not speed: protoPython at its best is still ~40× slower than single-threaded CPython")
ax.legend(ncol=4, loc="upper left", fontsize=11)
ax.grid(axis="x", visible=False)
save(fig, "10_best_time_per_runtime")
write_csv("headline_best_times", head_rows)

# ---------------------------------------------------------------- 11 granularity
fig, ax = plt.subplots(figsize=HALF)
width = .2
gran_rows = []
for i, rt in enumerate(RT):
    ys = [final[(b, rt, 1, 1)]["mean"] / final[(b, rt, 1, 1)]["expanded"] * 1e6 for b in BOARDS]
    xs = [j + (i - 1.5) * width for j in range(3)]
    ax.bar(xs, ys, width, color=COLOR[rt], label=SHORT[rt])
    for x, y in zip(xs, ys):
        ax.text(x, y * 1.1, f"{y:.0f}", ha="center", va="bottom", fontsize=9.5)
    for b, y in zip(BOARDS, ys):
        gran_rows.append({"board": b, "runtime": rt, "us_per_node_1_worker": round(y, 1)})
ax.set_yscale("log")
ax.set_ylim(1, 5000)
ax.set_xticks(range(3))
ax.set_xticklabels([BOARD_TITLE[b] for b in BOARDS])
ax.set_ylabel("µs per expanded node, 1 worker (log)")
ax.set_title("Task granularity: ~100× more work per node")
ax.legend(ncol=2, loc="upper left", fontsize=11)
ax.grid(axis="x", visible=False)
save(fig, "11_granularity_us_per_node")
write_csv("granularity", gran_rows)

# ---------------------------------------------------------------- 12 Amdahl
fig, axes = plt.subplots(1, 2, figsize=WIDE)
ax = axes[0]
ns = [1 + i * .1 for i in range(71)]
for s, ls in ((0.15, ":"), (0.25, "--"), (0.35, "-.")):
    ax.plot(ns, [1 / (s + (1 - s) / n) for n in ns], ls=ls, color="#999999", lw=1.6, label=f"Amdahl, serial fraction {s:.2f}")
ax.plot([1, 8], [1, 8], color="#CCCCCC", lw=1.2, label="ideal")
amdahl_rows = []
for board, mk in (("soko_01", "o"), ("microban", "s"), ("Patrick/P110", "^")):
    base = final[(board, "protopy", 1, 1)]["mean"]
    pts = {w: v for w, v in zip(*series(final, board, "protopy", 1))}
    if board != "Patrick/P110":
        pts.update({w: v for w, v in zip(*series(extra, board, "protopy", 1))})
    ws = sorted(pts)
    sp = [base / pts[w]["mean"] for w in ws]
    ax.plot(ws, sp, marker=mk, ms=8, lw=2, color=COLOR["protopy"], alpha=.55 + .15 * ["soko_01", "microban", "Patrick/P110"].index(board),
            label=f"protoPython, {BOARD_TITLE[board]}")
    sfs = [(w / s_ - 1) / (w - 1) for w, s_ in zip(ws, sp) if w > 1]
    axes[1].plot([w for w in ws if w > 1], sfs, marker=mk, ms=8, lw=2, color=COLOR["protopy"],
                 alpha=.55 + .15 * ["soko_01", "microban", "Patrick/P110"].index(board), label=f"protoPython, {BOARD_TITLE[board]}")
    for w, s_ in zip(ws, sp):
        amdahl_rows.append({"board": board, "workers": w, "speedup": round(s_, 3),
                            "serial_fraction": round((w / s_ - 1) / (w - 1), 3) if w > 1 else ""})
ax.set_xlim(1, 8)
ax.set_ylim(0.8, 8)
ax.set_xlabel("worker threads")
ax.set_ylabel("speedup over 1 worker")
ax.set_title("Measured speedup vs Amdahl's law")
ax.legend(fontsize=9.5, loc="upper left")
axes[1].set_xlabel("worker threads")
axes[1].set_ylabel("implied serial fraction  s = (n/S − 1)/(n − 1)")
axes[1].set_title("Serial fraction grows with threads → contention")
axes[1].set_ylim(0, .5)
axes[1].set_xticks(range(2, 9))
axes[1].legend(fontsize=10)
save(fig, "12_amdahl_serial_fraction")
write_csv("amdahl_protopy", amdahl_rows)

# ---------------------------------------------------------------- 13 oversubscription
fig, ax = plt.subplots(figsize=WIDE)
over_rows = []
for board, mk in (("soko_01", "o"), ("microban", "s")):
    for locks, ls in ((1, "-"), (0, "--")):
        ws, vs = series(over, board, "protopy", locks)
        ax.errorbar(ws, [v["mean"] for v in vs], yerr=[v["std"] for v in vs], ls=ls, marker=mk, ms=7, lw=2.2, capsize=3,
                    color=COLOR["protopy"] if board == "soko_01" else "#A0522D",
                    label=f"{board}, {'striped locks' if locks else 'no locks'}")
        for w, v in zip(ws, vs):
            over_rows.append({"board": board, "locks": locks, "workers": w, "mean_s": round(v["mean"], 2),
                              "expanded": round(v["expanded"]), "regressions": round(v["regressions"], 1)})
ax.axvline(8, color="#555555", lw=1.2, ls=":")
ax.text(8.4, 33, "8 CPU cores", color="#555555", fontsize=12)
ax.set_xscale("log", base=2)
ax.set_xticks([1, 2, 4, 8, 16, 32, 64, 128, 256])
ax.set_xticklabels(["1", "2", "4", "8", "16", "32", "64", "128", "256"])
ax.set_xlabel("worker threads (log₂)")
ax.set_ylabel("solve time (s) — mean ± std, 3 runs")
ax.set_ylim(0, 40)
ax.set_title("protoPython oversubscribed up to 256 threads: stable, correct, no further gain past 4–8")
ax.legend(fontsize=11)
save(fig, "13_oversubscription_protopy")
write_csv("oversubscription", over_rows)

# ---------------------------------------------------------------- 14 microbenchmarks
micro = defaultdict(dict)
for d in load(NIGHT / "micro/results.jsonl"):
    micro[d["bench_runtime"]][d["test"]] = d["ns_per_op"]
tests = [t for t in micro["cpython"] if t in micro["protopy"]]
tests.sort(key=lambda t: micro["protopy"][t] / micro["cpython"][t])
fig, ax = plt.subplots(figsize=WIDE)
ratios = [micro["protopy"][t] / micro["cpython"][t] for t in tests]
ratios_ft = [micro["cpython-ft"][t] / micro["cpython"][t] for t in tests]
y = range(len(tests))
ax.barh([i + .2 for i in y], ratios, .4, color=COLOR["protopy"], label="protoPython / CPython")
ax.barh([i - .2 for i in y], ratios_ft, .4, color=COLOR["cpython-ft"], label="CPython 3.14t (no GIL) / CPython")
for i, r in enumerate(ratios):
    ax.text(r * 1.1, i + .2, f"{r:.0f}×" if r >= 2 else f"{r:.1f}×", va="center", fontsize=10.5)
ax.axvline(1, color="#555555", lw=1)
ax.set_xscale("log")
ax.set_yticks(list(y))
ax.set_yticklabels(tests, family="monospace", fontsize=12)
ax.set_xlabel("time per operation relative to CPython 3.14 (log; 1× = same speed)")
ax.set_title("Where protoPython pays: tuple indexing, heapq and iteration are 100–220× slower; plain int loops are not")
ax.legend(loc="lower right")
ax.grid(axis="y", visible=False)
save(fig, "14_microbench_slowdown")
write_csv("microbench", [{"test": t, "cpython_ns": round(micro["cpython"][t], 1),
                          "cpython_ft_ns": round(micro["cpython-ft"][t], 1), "protopy_ns": round(micro["protopy"][t], 1),
                          "protopy_vs_cpython": round(micro["protopy"][t] / micro["cpython"][t], 1)} for t in tests])

# ---------------------------------------------------------------- 15 perf profile
CATS = [
    ("garbage collector (mark + sweep)", re.compile(r"sweep|Marker::|gcThreadLoop|shade"), "#7F8C8D"),
    ("cell allocation", re.compile(r"AllocCell|allocCell"), "#C0392B"),
    ("attribute / type lookup", re.compile(r"Attribute|getFirstParent|hasParent|getType|isActuallyAClass|InternedString|isString|getHash"), "#E67E22"),
    ("containers (sparse lists, tuples)", re.compile(r"SparseList|ProtoList|sparse_avl|tupleView"), "#F1C40F"),
    ("bytecode dispatch", re.compile(r"Activation::dispatch"), "#2980B9"),
]


def profile(path):
    acc = defaultdict(float)
    for line in path.read_text().splitlines():
        m = re.match(r"\s+([\d.]+)%\s+(\S+)\s+\[[.k]\]\s+(.*)", line)
        if not m:
            continue
        pct, sym = float(m[1]), m[3]
        for name, rx, _ in CATS:
            if rx.search(sym):
                acc[name] += pct
                break
        else:
            acc["everything else"] += pct
    acc["everything else"] += max(0.0, 100 - sum(acc.values()))
    return acc


prof = {w: profile(NIGHT / f"perf/report_w{w}.txt") for w in (1, 4)}
fig, ax = plt.subplots(figsize=WIDE)
names = [c[0] for c in CATS] + ["everything else"]
colors = [c[2] for c in CATS] + ["#D5D8DC"]
left = {1: 0.0, 4: 0.0}
for name, col in zip(names, colors):
    vals = [prof[1][name], prof[4][name]]
    ax.barh([1, 0], vals, left=[left[1], left[4]], color=col, label=name, height=.55)
    for yy, w, v in ((1, 1, vals[0]), (0, 4, vals[1])):
        if v >= 4:
            ax.text(left[w] + v / 2, yy, f"{v:.0f}%", ha="center", va="center", fontsize=12, color="white" if col not in ("#F1C40F", "#D5D8DC") else INK, weight="bold")
        left[w] += v
ax.set_yticks([1, 0])
ax.set_yticklabels(["1 worker", "4 workers"])
ax.set_xlim(0, 100)
ax.set_xlabel("% of CPU samples (perf, self time)")
ax.set_title("protoPython profile, soko_01: memory management dominates; the interpreter loop is ~2%")
ax.legend(ncol=3, loc="upper center", bbox_to_anchor=(.5, -.18), fontsize=11)
ax.grid(axis="y", visible=False)
save(fig, "15_protopy_profile")
write_csv("protopy_profile", [{"category": n, "w1_pct": round(prof[1][n], 1), "w4_pct": round(prof[4][n], 1)} for n in names])

# ---------------------------------------------------------------- 16 perf stat: CPU vs wall
def stat(path):
    t = path.read_text()
    get = lambda rx: float(re.search(rx, t)[1].replace(",", ""))
    return {"cpu_s": get(r"([\d.,]+) msec task-clock") / 1000, "wall_s": get(r"([\d.]+) seconds time elapsed"),
            "ctx": get(r"([\d,]+)\s+context-switches")}


st = {"protoPython, 1 worker": stat(NIGHT / "perf/stat_w1.txt"),
      "protoPython, 4 workers": stat(NIGHT / "perf/stat_w4.txt"),
      "3.14t no GIL, 4 workers": stat(NIGHT / "perf/stat_cpython_ft_w4.txt")}
fig, axes = plt.subplots(1, 2, figsize=WIDE)
keys = list(st)
cols = [COLOR["protopy"], COLOR["protopy"], COLOR["cpython-ft"]]
ax = axes[0]
ax.bar([i - .2 for i in range(3)], [st[k]["cpu_s"] for k in keys], .4, color=cols, alpha=.45, label="CPU time (all threads)")
ax.bar([i + .2 for i in range(3)], [st[k]["wall_s"] for k in keys], .4, color=cols, label="wall-clock time")
for i, k in enumerate(keys):
    ax.text(i - .2, st[k]["cpu_s"] + .5, f"{st[k]['cpu_s']:.1f}", ha="center", fontsize=11)
    ax.text(i + .2, st[k]["wall_s"] + .5, f"{st[k]['wall_s']:.1f}", ha="center", fontsize=11)
    ax.text(i, -6.5, f"{st[k]['cpu_s'] / st[k]['wall_s']:.1f} cores busy", ha="center", fontsize=11, color=MUTED)
ax.set_xticks(range(3))
ax.set_xticklabels([k.replace(", ", "\n") for k in keys], fontsize=12)
ax.set_ylabel("seconds (soko_01)")
ax.set_ylim(0, 45)
ax.set_title("Same CPU work,\nspread over more cores")
ax.legend(fontsize=11)
ax.grid(axis="x", visible=False)
ax = axes[1]
rates = [st[k]["ctx"] / st[k]["wall_s"] for k in keys]
ax.bar(range(3), rates, color=cols, width=.55)
for i, r in enumerate(rates):
    ax.text(i, r * 1.15, f"{r:,.0f}/s", ha="center", fontsize=12)
ax.set_yscale("log")
ax.set_ylim(10, 1e6)
ax.set_xticks(range(3))
ax.set_xticklabels([k.replace(", ", "\n") for k in keys], fontsize=12)
ax.set_ylabel("context switches per second (log)")
ax.set_title("Threads sleeping and waking\non the shared queue lock")
ax.grid(axis="x", visible=False)
save(fig, "16_cpu_vs_wall_context_switches")
write_csv("perf_stat", [{"run": k, **{kk: round(v, 3) for kk, v in st[k].items()}} for k in keys])

# ---------------------------------------------------------------- 17 locks vs no locks
fig, axes = plt.subplots(1, 3, figsize=WIDE, sharey=True)
for ax, board in zip(axes, BOARDS):
    for rt in ["cpython", "cpython-ft", "protopy"]:
        for locks, ls in ((0, "--"), (1, "-")):
            base = final[(board, rt, locks, 1)]["mean"]
            ws, vs = series(final, board, rt, locks)
            ax.plot(ws, [base / v["mean"] for v in vs], ls=ls, marker="o", lw=2.3, color=COLOR[rt],
                    label=f"{SHORT[rt]}, {'no locks' if not locks else 'striped locks'}")
    ax.axhline(1, color="#555555", lw=1)
    ax.set_title(BOARD_TITLE[board])
    ax.set_xticks(WORKERS)
    ax.set_xlabel("worker threads")
axes[0].set_ylabel("speedup over 1 worker")
handles, labels_ = axes[0].get_legend_handles_labels()
fig.legend(handles, labels_, ncol=3, loc="lower center", bbox_to_anchor=(.5, -.1), fontsize=12)
fig.suptitle("Striped locks remove every lost update at little or no cost (dashed = no locks, solid = locks)",
             fontsize=15, weight="bold")
save(fig, "17_locks_vs_no_locks")

# ---------------------------------------------------------------- 18 sequential algorithms
greedy = aggregate(load(NIGHT / "sequential_greedy/results.jsonl"))
bfs = aggregate(load(NIGHT / "sequential_bfs/results.jsonl"))
fig, axes = plt.subplots(1, 2, figsize=WIDE)
algo_rows = []
for j, board in enumerate(BOARDS):
    a = final[(board, "cpython", 0, 1)]
    g = greedy[(board, "cpython", 0, 1)]
    entries = [("A* (1 worker)", a, "#34495E"), ("greedy best-first", g, "#16A085")]
    if (board, "cpython", 0, 1) in bfs:
        entries.append(("BFS", bfs[(board, "cpython", 0, 1)], "#95A5A6"))
    for i, (name, v, col) in enumerate(entries):
        x = j + (i - 1) * .27
        axes[0].bar(x, v["steps"][0], .25, color=col, label=name if j == 0 or name == "BFS" else None)
        axes[0].text(x, v["steps"][0] + 1, str(v["steps"][0]), ha="center", fontsize=11)
        axes[1].bar(x, v["expanded"], .25, color=col)
        axes[1].text(x, v["expanded"] * 1.12, f"{v['expanded']:,.0f}", ha="center", fontsize=9.5)
        algo_rows.append({"board": board, "algorithm": name, "steps": v["steps"][0], "expanded": round(v["expanded"]),
                          "cpython_s": round(v["mean"], 4)})
for ax in axes:
    ax.set_xticks(range(3))
    ax.set_xticklabels([BOARD_TITLE[b] for b in BOARDS])
    ax.grid(axis="x", visible=False)
axes[0].set_ylabel("solution length (moves)")
axes[0].set_title("A* is optimal; greedy is not")
axes[0].legend(fontsize=11, loc="upper right")
axes[1].set_yscale("log")
axes[1].set_ylim(300, 400000)
axes[1].set_ylabel("nodes expanded (log)")
axes[1].set_title("…but greedy explores 5–80× fewer nodes")
save(fig, "18_sequential_algorithms")
write_csv("sequential_algorithms", algo_rows)

# ---------------------------------------------------------------- 19 protopyc status matrix
cases = ["clash", "pep695", "generic_base", "builtin_generic"]
case_label = {"clash": "two modules with\nsame-named method", "pep695": "PEP 695\nclass Box[T](Base[T])",
              "generic_base": "class C(Base[int])\n(typing.Generic)", "builtin_generic": "class L(list[int])"}
cols_ = [("protopyc", "default"), ("protopyc -Bsymbolic", "bsymbolic"), ("protoPython\ninterpreter", "interp"), ("CPython", "cpython")]
status = {}
sec = None
for line in (NIGHT / "block_8_protopyc.log").read_text().splitlines():
    if line.startswith("== link: default"):
        sec = "default"
    elif line.startswith("== link: bsymbolic"):
        sec = "bsymbolic"
    elif line.startswith("== CPython"):
        sec = "cpython"
    elif line.startswith("== interpreted"):
        sec = "interp"
    else:
        m = re.match(r"\s+(\w+): (.*)", line)
        if m and sec and m[1] in cases:
            status[(m[1], sec)] = m[2]
fig, ax = plt.subplots(figsize=WIDE)
for i, c in enumerate(cases):
    for j, (_, key) in enumerate(cols_):
        msg = status.get((c, key), "?")
        ok = " ok" in msg
        ax.add_patch(FancyBboxPatch((j + .05, i + .08), .9, .84, boxstyle="round,pad=0,rounding_size=.06",
                                    color="#D5F5E3" if ok else "#FADBD8", ec=GOOD if ok else BAD, lw=1.5))
        short = "✓ works" if ok else "✗ " + msg.split(":")[0]
        ax.text(j + .5, i + .5, short, ha="center", va="center", fontsize=12.5, weight="bold", color=GOOD if ok else BAD)
ax.set_xlim(0, 4)
ax.set_ylim(len(cases), 0)
ax.set_xticks([j + .5 for j in range(4)])
ax.set_xticklabels([c[0] for c in cols_], fontsize=13)
ax.xaxis.tick_top()
ax.set_yticks([i + .5 for i in range(len(cases))])
ax.set_yticklabels([case_label[c] for c in cases], fontsize=12)
ax.grid(False)
for s in ax.spines.values():
    s.set_visible(False)
ax.tick_params(length=0)
ax.set_title("protopyc (ahead-of-time compiler): minimal repros of the bugs found while compiling tp1", pad=50)
save(fig, "19_protopyc_bug_matrix")
write_csv("protopyc_matrix", [{"case": c, **{k: status.get((c, k), "") for _, k in cols_}} for c in cases])

# ---------------------------------------------------------------- 20 run scorecard
blocks = [
    ("correctness (960 runs, 4 runtimes,\nsolvable + unsolvable board)", "960 / 960 correct"),
    ("final scaling, soko_01 + microban\n(4 runtimes × 5 worker counts × 2 lock modes × 10)", "800 / 800 solved"),
    ("final scaling, P110", "400 / 400 solved"),
    ("crash hunt (protoPython, 8 workers)", "64 / 64 ok — earlier crash not reproduced"),
    ("oversubscription (protoPython, up to 256 threads)", "108 / 108 solved"),
    ("hash fix, old vs new protoPython", "old: soko_01 unsolved 6/6\nfixed: solved 6/6"),
]
fig, ax = plt.subplots(figsize=WIDE)
ax.axis("off")
ax.set_xlim(0, 1)
ax.set_ylim(len(blocks) + .6, 0)
for i, (what, res) in enumerate(blocks):
    bad = "unsolved" in res
    ax.add_patch(FancyBboxPatch((.01, i + .1), .98, .8, boxstyle="round,pad=0,rounding_size=.02",
                                color="#F8F9F9", ec="#D5D8DC"))
    ax.text(.03, i + .5, what, va="center", fontsize=13)
    ax.text(.97, i + .5, res, va="center", ha="right", fontsize=13, weight="bold", color="#B9770E" if bad else GOOD)
ax.text(.5, len(blocks) + .35, "night of 2026-11-02 · 217 min · 8-core laptop · 0 timeouts · 0 errors",
        ha="center", fontsize=12, color=MUTED)
ax.set_title("Overnight benchmark run: every block completed", fontsize=17)
save(fig, "20_night_run_scorecard")

print(f"\nfigures in {OUT}\ndata in {DATA}")
