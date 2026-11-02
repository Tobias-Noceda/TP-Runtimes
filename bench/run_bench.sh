#!/usr/bin/env bash
# Benchmarks tp1 across runtimes and worker counts, then plots mean ± std.
#
#   bench/run_bench.sh                        # defaults below
#   RUNS=5 WORKERS="1 4" BOARDS=soko_01 bench/run_bench.sh
#   bench/run_bench.sh --plot-only bench/results/<dir>
#
# Every knob is an environment variable:
#   RUNS       samples per (runtime, board, workers)        default 3
#   BOARDS     names under res/boards/ (without .json)      default "soko_01 microban"
#   ALGORITHM  a_star | greedy | bfs                        default a_star
#   HEURISTIC  trivial | closest | reduction                default reduction
#   WORKERS    A* worker threads (ignored by greedy/bfs)    default "1 2 4 8"
#   LOCKS      A* race fix: "0", "1" or "0 1" (both)      default 0
#   RUNTIMES   any of: cpython cpython-ft cpython-ft-gil protopy
#              (cpython-ft-gil = the 3.14t build with PYTHON_GIL=1)
#                                                           default "cpython cpython-ft protopy"
#   TIMEOUT    seconds per sample                           default 600
#   CPYTHON, CPYTHON_FT, PROTOPY   interpreter paths (auto-detected)
#   OUT        results directory                            default bench/results/<timestamp>
set -euo pipefail
export LC_ALL=C

HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
ROOT=$(dirname "$HERE")

plot() {
    # The plots run on uv's CPython with matplotlib, never on protopy.
    uv run --no-project --python 3.14 --with matplotlib python -I "$HERE/plot.py" "$1"
}

if [[ "${1:-}" == "--plot-only" ]]; then
    plot "${2:?usage: run_bench.sh --plot-only <results dir>}"
    exit 0
fi

RUNS=${RUNS:-3}
BOARDS=${BOARDS:-"soko_01 microban"}
ALGORITHM=${ALGORITHM:-a_star}
HEURISTIC=${HEURISTIC:-reduction}
WORKERS=${WORKERS:-"1 2 4 8"}
LOCKS=${LOCKS:-0}
RUNTIMES=${RUNTIMES:-"cpython cpython-ft protopy"}
TIMEOUT=${TIMEOUT:-600}
CPYTHON=${CPYTHON:-$(command -v python3.14 || true)}
CPYTHON_FT=${CPYTHON_FT:-$(uv python find 3.14t 2>/dev/null || true)}
PROTOPY=${PROTOPY:-$ROOT/../protoPython/build_release/src/runtime/protopy}
OUT=${OUT:-$HERE/results/$(date +%Y%m%d-%H%M%S)}

[[ "$ALGORITHM" == "a_star" ]] || { WORKERS=1; LOCKS=0; }

interpreter() {
    case "$1" in
        cpython) echo "$CPYTHON" ;;
        cpython-ft | cpython-ft-gil) echo "$CPYTHON_FT" ;;
        protopy) echo "$PROTOPY" ;;
        *) echo "unknown runtime $1" >&2; exit 1 ;;
    esac
}

for rt in $RUNTIMES; do
    bin=$(interpreter "$rt")
    [[ -n "$bin" && -x "$bin" ]] || { echo "runtime $rt: no interpreter (got '$bin')" >&2; exit 1; }
done
for b in $BOARDS; do
    [[ -f "$ROOT/res/boards/$b.json" ]] || { echo "no board res/boards/$b.json" >&2; exit 1; }
done

mkdir -p "$OUT"
OUT=$(cd "$OUT" && pwd)
RESULTS=$OUT/results.jsonl
: > "$RESULTS"

{
    echo "date: $(date -Iseconds)"
    echo "host: $(uname -srm), $(nproc) CPUs"
    echo "config: RUNS=$RUNS BOARDS='$BOARDS' ALGORITHM=$ALGORITHM HEURISTIC=$HEURISTIC WORKERS='$WORKERS' LOCKS='$LOCKS' TIMEOUT=$TIMEOUT"
    for repo in "$ROOT" "$ROOT/../protoPython" "$ROOT/../protoCore"; do
        [[ -d "$repo/.git" ]] || continue
        dirty=$(git -C "$repo" status --porcelain --untracked-files=no | wc -l)
        echo "repo $(basename "$(cd "$repo" && pwd)"): $(git -C "$repo" rev-parse --abbrev-ref HEAD)@$(git -C "$repo" rev-parse --short HEAD) ($dirty modified files)"
    done
    for rt in $RUNTIMES; do
        echo "runtime $rt: $(interpreter "$rt")"
    done
} > "$OUT/meta.txt"
cat "$OUT/meta.txt"

total=$(( RUNS * $(wc -w <<< "$RUNTIMES") * $(wc -w <<< "$BOARDS") * $(wc -w <<< "$WORKERS") * $(wc -w <<< "$LOCKS") ))
n=0

# Repetitions are the outer loop so that a slow drift of the machine (thermal,
# background load) spreads over every variant instead of biasing one.
for run in $(seq 1 "$RUNS"); do
    for board in $BOARDS; do
        for workers in $WORKERS; do
          for locks in $LOCKS; do
            for rt in $RUNTIMES; do
                n=$((n + 1))
                bin=$(interpreter "$rt")
                args=("$HERE/runner.py" "$ROOT/res/boards/$board.json" "$ALGORITHM" "$HEURISTIC" "$workers" "$locks")
                env_gil=()
                [[ "$rt" == "cpython-ft" ]] && env_gil=(PYTHON_GIL=0)
                [[ "$rt" == "cpython-ft-gil" ]] && env_gil=(PYTHON_GIL=1)

                set +e
                # Run from the results directory: an interpreter must not pick
                # up modules from the current directory.
                line=$(cd "$OUT" && env "${env_gil[@]}" timeout "$TIMEOUT" "$bin" "${args[@]}" 2> "$OUT/last_stderr.txt" | tail -n 1)
                status=$?
                set -e

                if [[ $status -eq 124 ]]; then
                    sample="{\"status\": \"timeout\", \"seconds\": null}"
                elif [[ $status -ne 0 || "$line" != \{* ]]; then
                    # exit code > 128 = killed by signal (139 = SIGSEGV, 134 = SIGABRT)
                    { cat "$OUT/last_stderr.txt"; echo "exit code: $status"; } > "$OUT/error_${rt}_${board//\//_}_${workers}_l${locks}_${run}.txt"
                    sample="{\"status\": \"error\", \"exit_code\": $status, \"seconds\": null}"
                else
                    sample="{\"status\": \"ok\", ${line:1}"
                fi
                sample="${sample%\}}, \"runtime\": \"$rt\", \"board\": \"$board\", \"algorithm\": \"$ALGORITHM\", \"heuristic\": \"$HEURISTIC\", \"workers\": $workers, \"locks\": $locks, \"run\": $run}"
                echo "$sample" >> "$RESULTS"
                printf '[%d/%d] run %d  %-8s w=%-3s l=%s %-15s %s\n' "$n" "$total" "$run" "$board" "$workers" "$locks" "$rt" \
                    "$(sed -E 's/.*"status": "([a-z]+)".*"seconds": ([0-9.]+|null).*/\1 \2 s/' <<< "$sample")"
            done
          done
        done
    done
done
rm -f "$OUT/last_stderr.txt"

plot "$OUT"
