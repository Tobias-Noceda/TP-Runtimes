# Slide brief — Parallel A* for Sokoban on four Python runtimes

> **For Claude Design.** Build a 16:9 slide deck from this brief. Every chart already exists as a
> PNG (and an SVG) in `figures/`; use them as they are, don't redraw them. The exact numbers are in
> `data/*.csv`. Each slide below gives a title, the figure(s) to use, the on-slide text (keep it this
> short), and speaker notes. **Don't add claims that aren't in this brief.**
> Language: English as written. If a Spanish deck is needed, translate the slide text only and keep
> the chart files as they are.

## Context

- **Course:** Runtimes Concurrentes (ITBA), final presentation. Audience: classmates and professors
  who know threads, locks, GIL, Amdahl's law, and hashing.
- **Project:** we took a Sokoban solver (TP1 of another course: A\* over game states, written in
  Python), made A\* **multi-threaded**, and ran it on four runtimes:

| short name | runtime | GIL |
|---|---|---|
| CPython | CPython 3.14.7 | yes |
| 3.14t + GIL | CPython 3.14t free-threaded build, GIL forced on (`PYTHON_GIL=1`) | yes |
| 3.14t no GIL | CPython 3.14t free-threaded build | no |
| protoPython | protoPython (interpreter on top of the protoCore runtime, immutable objects + CAS) | no |

- **Hardware:** one 8-core Linux laptop. The overnight benchmark took 217 min, with 0 timeouts and 0 errors.
- **Parallel A\* design:** N worker threads share one `queue.PriorityQueue` (the open set) and two dicts
  (`smallest_g_score`, `previous_state`). Optional **64 striped locks** (stripe = `hash(state) & 63`)
  make "check g-score → write g-score + parent" atomic per state.

## Story in one line

**Removing the GIL is necessary but not sufficient: only protoPython actually scales (2.3–2.6×). But
it starts ~100× slower per node, and getting it to give correct answers first meant fixing a hash
bug in the runtime.**

## Visual style

- Clean, technical, light background. Charts have white backgrounds, so put them on white or very
  light cards.
- **Keep the runtime colors the charts use** in any accents or legends:
  CPython `#4C72B0` (blue) · 3.14t + GIL `#8172B3` (purple) · 3.14t no GIL `#55A868` (green) ·
  protoPython `#DD8452` (orange). Bad/bug `#C0392B`, good/fixed `#2E8B57`.
- One idea per slide. Big number callouts where noted (★).
- Code in monospace. Don't use stock imagery.

---

## Slide outline (≈16 slides, ~15 min)

### 1. Title
**Parallel A\* on four Python runtimes**: what removing the GIL actually buys you.
Subtitle: Sokoban solver · CPython 3.14, 3.14t (free-threaded), protoPython · Runtimes Concurrentes, ITBA.
Optional background: `figures/01_benchmark_boards.png` (cropped/faded).

### 2. The problem: Sokoban as a search
Figure: `01_benchmark_boards.png`
- State = (player position, box positions), as nested tuples, hashed into dicts and sets
- A\* with an admissible heuristic → optimal solution
- 3 benchmark boards: soko_01 (78 moves), microban (63), P110 (51). P110 uses the trivial heuristic, so it expands ~97k nodes.
Notes: the hashing of nested tuples matters later (slide 5).

### 3. Making A\* parallel
No chart. Draw a simple diagram: N worker threads → one shared priority queue (open set) → shared
`g_score` / `parent` dicts. Highlight the race:
```python
if tentative < g[next]:      # check
    g[next] = tentative      # act  ← another thread can write in between
    parent[next] = current
```
- Without a GIL this check-then-act loses updates.
- Fix: 64 striped locks keyed by `hash(state)`.

### 4. Four runtimes
Table from Context above, plus one line per runtime:
CPython = baseline · 3.14t + GIL = same build, isolates the GIL's effect · 3.14t no GIL = official free-threading · protoPython = experimental runtime, no GIL by design.

### 5. Bug #1: two states, one hash ★
Figure: `02_hash_collision_example.png`
- protoPython's old tuple hash `h = h·1000003 ^ hash(item)` cancels across nesting levels
- `((0,0),((0,1),(0,2)))` and `((0,1),((0,0),(0,2)))` (player and a box swapped) get the same hash
- protoCore treated equal tuple hashes as equal keys, so set/dict **merged different states**
- Fix: xxHash-style mixing in protoCore + protoPython (branch `fix/tuple-hash-xxhash`) + regression tests

### 6. Bug #1: impact ★
Figures: `03_hash_bug_states_lost.png` (left) + `04_hash_bug_soko01_unsolvable.png` (right, or its own slide)
- Big number: **35% of states silently lost** (7,506 of 21,420 on a 6×6 grid; 43,103 of 124,992 on 8×8)
- soko_01 on old protoPython: **"no solution"** after 14,602 nodes, in 6 of 6 runs. Fixed: 78-move optimal solution.
- The benchmark harness logged those runs as "ok", because the process exited cleanly. We now count *solved* separately.
Notes: a wrong answer that comes back fast looks like a performance win. Check correctness before timing anything.

### 7. Atomic operations vs atomic logic
Figure: `05_lost_updates_microbench.png`
- Each thread adds its own keys to dict / set / list → **0 lost** on every runtime: single operations are atomic
- `d[k] += 1` on one shared key → **48–89% of updates lost** without a GIL (2→16 threads); 0% with the GIL
- protoPython makes each container op atomic with a CAS on an immutable snapshot. That doesn't help a read-then-write sequence.

### 8. The same race inside A\*
Figure: `06_astar_lost_updates.png`
- Without locks: up to ~2,400 (soko_01), ~2,100 (microban) and ~9,200 (P110) lost g-score updates per solve at 8 threads
- With the GIL: ≈ 0–13 (the GIL still switches threads, just rarely in the middle of this sequence)
- With striped locks: **0 on every runtime and board**
Notes: an earlier run also produced a **non-optimal path** on board1 (7 moves instead of 5, 3.14t, 8 workers). Lost updates can break A\*'s optimality, not just slow it down.

### 9. Lost updates = wasted work
Figure: `07_astar_wasted_work.png`
- No locks, no GIL: 5–9% extra nodes expanded at 8 threads
- With locks: same node count as sequential (±0.1%)

### 10. Does it scale? ★
Figure: `09_speedup_vs_workers.png` (main). Backup: `08_time_vs_workers.png`
- **protoPython: 2.3× (soko_01), 2.6× (microban), 2.3× (P110)**, with a plateau from 4–6 threads
- CPython with a GIL: ~1.1× (the GIL serialises execution)
- 3.14t without a GIL: **gets slower**, down to 0.76× at 8 threads
Notes: in 3.14t a node costs ~9 µs, so threads mostly contend on the queue lock (slide 13).

### 11. Locks are (almost) free
Figure: `17_locks_vs_no_locks.png`
- protoPython and 3.14t: locks give the same or *better* scaling, because fewer lost updates means less re-expanded work
- CPython with a GIL: locks cost a few percent (microban 1.17× → 1.08×)
- Keep the locks: they guarantee correctness.

### 12. Why the plateau? Amdahl
Figure: `12_amdahl_serial_fraction.png`
- The speedup fits Amdahl's law with serial fraction s ≈ 0.15–0.27 at 2–4 threads
- But the implied s **grows** with threads (0.15 → 0.39). That points to contention, not a fixed serial part.
- Serial suspects: the single `PriorityQueue` lock (with pure-Python `heapq` running inside it) and the shared allocator / GC

### 13. Why does 3.14t get slower? Granularity
Figures: `11_granularity_us_per_node.png` + `16_cpu_vs_wall_context_switches.png`
- Work per node: **~8–11 µs on CPython / 3.14t vs ~700–1,000 µs on protoPython**
- At 9 µs per node, threads spend their time handing off the queue lock: 87,000 context switches/s
- protoPython has ~100× more work per node, so the queue lock is a smaller share. Same CPU-seconds (37 → 38 s), spread over 3.9 cores, wall time 22.8 → 9.8 s
Notes: protoPython at 1 worker already keeps 1.6 cores busy, because of its concurrent GC thread.

### 14. Scaling is not speed ★
Figure: `10_best_time_per_runtime.png`
- Big number: **best protoPython time ≈ 40× slower than single-threaded CPython** (9.4 s vs 0.23 s on soko_01)
- At 1 worker protoPython is ~90× slower (21.3 s vs 0.23 s), so breaking even would take ~90 cores scaling perfectly

### 15. Where protoPython spends its time
Figures: `15_protopy_profile.png` + `14_microbench_slowdown.png`
- perf: **GC 37% + cell allocation 24%** at 1 worker; attribute/type lookup 16–26%; bytecode dispatch only 1–2%
- Microbenchmarks vs CPython: tuple index 220×, heappush/pop 158×, PriorityQueue 128×, enumerate 126×; plain int loop 1.0×
- So the cost is the object model and memory management (immutable cells, attribute lookup through prototype chains), not the interpreter loop
- Next step identified: a native `heapq` (the queue lock is held while pure-Python heapq runs)

### 16. Robustness
Figures: `13_oversubscription_protopy.png` + `20_night_run_scorecard.png`
- protoPython oversubscribed up to 256 threads on 8 cores: every run correct, time stays flat (no collapse)
- An intermittent silent exit seen earlier (P110, 8 workers) **did not reproduce** in 64 targeted runs. Still listed as open.

### 17. (Optional) protopyc, the ahead-of-time compiler
Figure: `19_protopyc_bug_matrix.png`
- We also tried compiling tp1 with protopyc. 4 minimal repros:
  1. symbol clash between modules (fixed by linking with `-Bsymbolic`)
  2. PEP 695 generics
  3. `typing.Generic` bases
  4. `list[int]` as a base (this one also fails in the interpreter)

### 18. Findings & contributions
Table (from `FINDINGS.md`, condensed):

| # | Finding | Status |
|---|---|---|
| F1 | Nested tuple hash collisions → states merged, solvable board reported unsolvable | **fixed** (protoCore + protoPython, xxHash, tests) |
| F4 | A\* hang on unsolvable boards | **fixed** (queue shutdown) |
| F5 | Check-then-act race in parallel A\* → lost updates, non-optimal paths | **fixed** (striped locks) |
| F6 | Container ops atomic without GIL; `+=` not | documented behaviour |
| F2, F3 | `@dataclass` without annotations; name mangling in comprehensions | workarounds |
| F7 | Intermittent silent exit (P110, 8 workers) | open, not reproduced |
| F8 | `sys._is_gil_enabled()` returns True on protoPython | open (cosmetic) |
| F9–F13 | protopyc: symbol clash, PEP 695, generic bases; `list[int]` base | open, repros ready |

### 19. Conclusions
1. **No GIL ≠ parallel speedup.** With fine-grained tasks (µs per node), the shared queue lock limits throughput, and 3.14t gets slower with more threads.
2. **No GIL = your races become real.** Single container operations stay atomic; multi-step logic doesn't. Striped locks fixed it at little or no cost.
3. **protoPython scales (2.3–2.6×)** but pays ~100× per node in allocation, GC and lookups. Scaling is not speed.
4. **Check correctness before timing.** A runtime hash bug made a solvable board "unsolvable", and that showed up looking like a speedup.

### 20. Thanks / Q&A
Backup slides (after Q&A): `08_time_vs_workers.png`, `18_sequential_algorithms.png` (A\* vs greedy vs BFS:
greedy expands 5–80× fewer nodes but gives 6–23% longer solutions), `13_oversubscription_protopy.png`.

---

## Caveats: do NOT claim

- Don't say locks cost "nothing" on CPython with the GIL. They cost a few percent there (slide 11).
- Speedups are relative to **the same runtime at 1 worker**, never across runtimes.
- The "3.14t + GIL" series in the scaling charts is valid. Lost-update and micro-benchmark numbers for
  3.14t + GIL are **left out** on purpose: the night script launched that runtime with `python -I`,
  which ignores `PYTHON_GIL`, so those blocks actually ran without a GIL. The script is fixed now
  (`-X gil=1`).
- protoPython reports version `3.14.0` and `gil=True` (finding F8). It actually runs without a GIL.
- The perf profile is one run per worker count (soko_01). Present percentages as rounded and approximate.
- Error bars: final scaling uses 10 runs per point; oversubscription 3; extra worker counts (3, 5, 7) 5.

## Files in this kit

| path | what |
|---|---|
| `BRIEF.md` | this document |
| `figures/NN_*.png` / `.svg` | 20 charts, 200 dpi PNG + vector SVG |
| `data/*.csv` | numbers behind every chart (`scaling_all_runtimes.csv` = full table) |
| `FINDINGS.md` | full findings log with root-cause notes |
| `make_figures.py` | regenerates figures/data from `bench/results/night-20261102-0108` |

Figure index: 01 boards · 02 hash collision example · 03 states lost by hash bug · 04 soko_01 old vs
fixed · 05 lost updates microbench · 06 A\* lost updates · 07 wasted work · 08 time vs workers ·
09 speedup · 10 best time per runtime · 11 µs per node · 12 Amdahl · 13 oversubscription ·
14 microbench slowdown · 15 perf profile · 16 CPU vs wall / context switches · 17 locks vs no locks ·
18 sequential algorithms · 19 protopyc bug matrix · 20 night scorecard.
