#!/usr/bin/env bash
# Overnight measurement of everything in the project, block by block, each in
# its own directory under bench/results/night-<date>/. A failing block is
# logged and the next one still runs; a block that would start after DEADLINE
# (default 6h45m from launch) is skipped. Estimated total: ~5.5 h on 8 CPUs.
#
#   systemd-inhibit --what=sleep:idle:handle-lid-switch \
#       nohup bench/night.sh > bench/results/night.log 2>&1 &
#
# Profiling (block 1) needs kernel.perf_event_paranoid <= 2, else it is skipped:
#   sudo sysctl -w kernel.perf_event_paranoid=1
#
# ONLY_BLOCKS="3 4" bench/night.sh    runs a subset (numbers below)
#
# Blocks:
#   0 correctness     unsolvable board (hang fix), board1 optimality x20, lost-update demo
#   1 profile         perf stat/record of protopy, 1 vs 4 workers
#   2 micro           microbenchmarks, all runtimes
#   3 final_reduction A*, soko_01 + microban, all runtimes, w 1-8, locks 0/1, 10 runs
#   4 final_p110      A*, Patrick/P110 trivial heuristic, same matrix
#   5 sequential      greedy (3 boards) and bfs (soko_01): no threads
#   6 crash_hunt      protopy w=8 repeated, exit codes (intermittent crash)
#   7 hash_fix        build protoPython/protoCore before the tuple-hash fix and
#                     compare old vs fixed protopy (collisions, tp1 results)
#   8 protopyc        protopyc bug repro (symbol clash, PEP 695, generic bases)
#   9 oversubscribed  protopy w 1..256, locks 0/1, 3 runs
#  10 extra_workers   protopy w 3 5 7, locks 0/1, 5 runs
set -uo pipefail
export LC_ALL=C

HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
ROOT=$(dirname "$HERE")
PROJECT=$(dirname "$ROOT")
NIGHT=${NIGHT:-$HERE/results/night-$(date +%Y%m%d-%H%M)}
PROTOPY=${PROTOPY:-$PROJECT/protoPython/build_release/src/runtime/protopy}
CPYTHON=${CPYTHON:-$(command -v python3.14)}
CPYTHON_FT=${CPYTHON_FT:-$(uv python find 3.14t 2>/dev/null)}
ALL_RUNTIMES="cpython cpython-ft-gil cpython-ft protopy"
ONLY_BLOCKS=${ONLY_BLOCKS:-"0 1 2 3 4 5 6 7 8 9 10"}
DEADLINE=${DEADLINE:-$(( 7 * 3600 ))}
# Commits that fixed the tuple hash; block 7 builds their parents.
FIX_PYTHON=${FIX_PYTHON:-4acd5b49}
FIX_CORE=${FIX_CORE:-4d8e4876}
mkdir -p "$NIGHT"

log() { echo "[$(date +%H:%M:%S)] $*"; }
wanted() { [[ " $ONLY_BLOCKS " == *" $1 "* ]]; }

block() {
    # block <number> <name> <function> [args...]
    local number=$1 name=$2; shift 2
    wanted "$number" || { log "block $number ($name): skipped (ONLY_BLOCKS)"; return; }
    if (( SECONDS > DEADLINE )); then log "block $number ($name): skipped (deadline)"; return; fi
    log "block $number ($name): start"
    local started=$SECONDS
    # Subshell: a block that cd-s or fails cannot affect the next one.
    if ( "$@" ) > >(tee "$NIGHT/block_${number}_$name.log") 2>&1; then
        log "block $number ($name): done in $(( (SECONDS - started) / 60 )) min"
    else
        log "block $number ($name): FAILED (exit $?) after $(( (SECONDS - started) / 60 )) min"
    fi
}

bench() {
    # bench <out subdir> VAR=value ...   (run_bench.sh with those settings)
    local out=$1; shift
    env "$@" OUT="$NIGHT/$out" "$HERE/run_bench.sh"
}

# Each runtime as a command line (3.14t needs PYTHON_GIL in the environment).
runtime_cmd() {
    case "$1" in
        cpython) echo "$CPYTHON -I" ;;
        cpython-ft-gil) echo "env PYTHON_GIL=1 $CPYTHON_FT -I" ;;
        cpython-ft) echo "env PYTHON_GIL=0 $CPYTHON_FT -I" ;;
        protopy) echo "$PROTOPY" ;;
        *) echo "$1" ;;
    esac
}

correctness() {
    local out=$NIGHT/correctness
    mkdir -p "$out"
    cd "$out" || return 1
    for rt in $ALL_RUNTIMES; do
        local cmd
        cmd=$(runtime_cmd "$rt")
        for workers in 1 4 8; do
            for locks in 0 1; do
                # 20 repetitions: how often does the race give a non-optimal
                # path (board1 optimum: 5 steps) with and without locks?
                for rep in $(seq 1 20); do
                for board in "$HERE/boards/unsolvable.json" "$ROOT/res/boards/board1.json"; do
                    local line status
                    line=$(timeout 60 $cmd "$HERE/runner.py" "$board" a_star reduction "$workers" "$locks" 2>&1 | tail -1)
                    status=$?
                    echo "{\"runtime\": \"$rt\", \"board\": \"$(basename "$board" .json)\", \"workers\": $workers, \"locks\": $locks, \"rep\": $rep, \"exit\": $status, \"result\": $([[ $line == \{* ]] && echo "$line" || echo "null")}"
                done
                done
            done
        done
    done | tee results.jsonl
    for rt in $ALL_RUNTIMES; do
        for threads in 2 4 8 16; do
            for rep in 1 2 3 4 5; do
                echo "## $rt threads=$threads rep=$rep"
                timeout 300 $(runtime_cmd "$rt") "$HERE/lostwrites.py" "$threads" 5000
            done
        done
    done | tee lostwrites.txt
}

profile() {
    local out=$NIGHT/perf
    mkdir -p "$out"
    command -v perf > /dev/null || { echo "perf not installed"; return 1; }
    local paranoid
    paranoid=$(cat /proc/sys/kernel/perf_event_paranoid)
    if (( paranoid > 2 )); then
        echo "kernel.perf_event_paranoid=$paranoid: run 'sudo sysctl -w kernel.perf_event_paranoid=1' to profile"
        return 1
    fi
    local board=$ROOT/res/boards/soko_01.json
    cd "$out" || return 1
    for workers in 1 4; do
        perf stat -e task-clock,context-switches,cpu-migrations,page-faults \
            -o "stat_w$workers.txt" "$PROTOPY" "$HERE/runner.py" "$board" a_star reduction "$workers" 0 || return 1
        perf record -F 499 -g -o "w$workers.data" "$PROTOPY" "$HERE/runner.py" "$board" a_star reduction "$workers" 0 || return 1
        perf report -i "w$workers.data" --stdio --no-children --sort dso,symbol 2> /dev/null | head -300 > "report_w$workers.txt"
    done
    # Same on CPython for reference (time split between interpreter and lock).
    perf stat -e task-clock,context-switches,cpu-migrations -o stat_cpython_ft_w4.txt \
        env PYTHON_GIL=0 "$CPYTHON_FT" -I "$HERE/runner.py" "$board" a_star reduction 4 0
}

micro() {
    local out=$NIGHT/micro
    mkdir -p "$out"
    cd "$out" || return 1
    for rt in $ALL_RUNTIMES; do
        echo "## $rt"
        timeout 900 $(runtime_cmd "$rt") "$HERE/micro.py" 20000 5 | sed "s/}$/, \"bench_runtime\": \"$rt\"}/" | tee -a results.jsonl
    done
}

crash_hunt() {
    # The intermittent no-output exit seen once on Patrick/P110 with 8 workers.
    bench crash_hunt_soko RUNS=30 RUNTIMES=protopy WORKERS=8 LOCKS="0 1" \
        BOARDS=soko_01 HEURISTIC=reduction TIMEOUT=600
    bench crash_hunt_p110 RUNS=4 RUNTIMES=protopy WORKERS=8 LOCKS=0 \
        BOARDS=Patrick/P110 HEURISTIC=trivial TIMEOUT=1200
}

hash_fix() {
    local out=$NIGHT/hash_fix old=$NIGHT/hash_fix/src
    mkdir -p "$old/protoPython" "$old/protoCore"
    # Sources of the commits right before the fix; the working repos are not touched.
    git -C "$PROJECT/protoPython" archive "$FIX_PYTHON^" | tar -x -C "$old/protoPython" || return 1
    git -C "$PROJECT/protoCore" archive "$FIX_CORE^" | tar -x -C "$old/protoCore" || return 1
    echo "old protoPython: $(git -C "$PROJECT/protoPython" rev-parse --short "$FIX_PYTHON^"), old protoCore: $(git -C "$PROJECT/protoCore" rev-parse --short "$FIX_CORE^")"
    cmake -S "$old/protoPython" -B "$old/build" -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_DISABLE_FIND_PACKAGE_protoCore=ON > "$out/cmake.log" 2>&1 || { tail -20 "$out/cmake.log"; return 1; }
    local started=$SECONDS
    cmake --build "$old/build" --target protopy -j "$(nproc)" > "$out/build.log" 2>&1 || { tail -30 "$out/build.log"; return 1; }
    echo "old protopy built in $(( (SECONDS - started) / 60 )) min"
    local old_protopy=$old/build/src/runtime/protopy

    cd "$out" || return 1
    for pair in "fixed:$PROTOPY" "old:$old_protopy" "cpython:$CPYTHON"; do
        local label=${pair%%:*} bin=${pair#*:}
        echo "## $label: hash collisions (6x6 and 8x8 grids)"
        timeout 900 "$bin" "$HERE/hash_collisions.py" 6 6
        timeout 900 "$bin" "$HERE/hash_collisions.py" 8 8
        echo "## $label: protoPython regression test tuple_hash_nested.py (from the fixed tree)"
        timeout 300 "$bin" "$PROJECT/protoPython/test/regression/tuple_hash_nested.py" 2>&1 | tail -3
        echo "## $label: micro hash/dict"
        timeout 600 "$bin" "$HERE/micro.py" 20000 5 hash_nested_tuple,dict_set_get_tuple_key,set_add_contains
    done | tee collisions.txt

    # tp1 on the old runtime: same boards as the main result, 1 and 4 workers, 3 runs.
    bench hash_fix/tp1_old RUNS=3 RUNTIMES=protopy PROTOPY="$old_protopy" WORKERS="1 4" LOCKS=0 \
        BOARDS="board1 soko_01 microban" HEURISTIC=reduction TIMEOUT=900
    bench hash_fix/tp1_fixed RUNS=3 RUNTIMES=protopy WORKERS="1 4" LOCKS=0 \
        BOARDS="board1 soko_01 microban" HEURISTIC=reduction TIMEOUT=900
}

protopyc() {
    "$HERE/protopyc_repro/repro.sh" "$NIGHT/protopyc"
}

{
    echo "night: $(date -Iseconds), $(nproc) CPUs, blocks '$ONLY_BLOCKS', deadline $(( DEADLINE / 60 )) min"
    for repo in "$ROOT" "$PROJECT/protoPython" "$PROJECT/protoCore"; do
        [[ -d "$repo/.git" ]] || continue
        dirty=$(git -C "$repo" status --porcelain --untracked-files=no | wc -l)
        echo "repo $(basename "$repo"): $(git -C "$repo" rev-parse --abbrev-ref HEAD)@$(git -C "$repo" rev-parse --short HEAD) ($dirty modified files)"
        (( dirty == 0 )) || echo "  WARNING: uncommitted changes in $repo; meta.txt will not pin the code"
    done
    echo "cpython: $CPYTHON"
    echo "cpython-ft: $CPYTHON_FT"
    echo "protopy: $PROTOPY"
} | tee "$NIGHT/night_meta.txt"

block 0 correctness correctness
block 1 profile profile
block 2 micro micro
block 3 final_reduction bench final_reduction \
    RUNS=10 RUNTIMES="$ALL_RUNTIMES" WORKERS="1 2 4 6 8" LOCKS="0 1" \
    BOARDS="soko_01 microban" HEURISTIC=reduction TIMEOUT=900
block 4 final_p110 bench final_p110_trivial \
    RUNS=10 RUNTIMES="$ALL_RUNTIMES" WORKERS="1 2 4 6 8" LOCKS="0 1" \
    BOARDS="Patrick/P110" HEURISTIC=trivial TIMEOUT=1200
block 5 sequential_greedy bench sequential_greedy \
    RUNS=5 RUNTIMES="$ALL_RUNTIMES" ALGORITHM=greedy \
    BOARDS="soko_01 microban Patrick/P110" HEURISTIC=reduction TIMEOUT=900
block 5 sequential_bfs bench sequential_bfs \
    RUNS=3 RUNTIMES="$ALL_RUNTIMES" ALGORITHM=bfs BOARDS="soko_01" TIMEOUT=900
block 6 crash_hunt crash_hunt
block 7 hash_fix hash_fix
block 8 protopyc protopyc
block 9 oversubscribed bench oversubscribed \
    RUNS=3 RUNTIMES=protopy WORKERS="1 2 4 8 16 32 64 128 256" LOCKS="0 1" \
    BOARDS="soko_01 microban" HEURISTIC=reduction TIMEOUT=900
block 10 extra_workers bench extra_workers \
    RUNS=5 RUNTIMES=protopy WORKERS="3 5 7" LOCKS="0 1" \
    BOARDS="soko_01 microban" HEURISTIC=reduction TIMEOUT=900

{
    echo "== summary"
    for f in "$NIGHT"/*/results.jsonl "$NIGHT"/*/*/results.jsonl; do
        [[ -f "$f" ]] || continue
        printf '%-60s samples %4d  ok %4d  timeout %3d  error %3d\n' "${f#$NIGHT/}" \
            "$(wc -l < "$f")" "$(grep -c '"status": "ok"' "$f")" \
            "$(grep -c '"status": "timeout"' "$f")" "$(grep -c '"status": "error"' "$f")"
    done
    ls "$NIGHT"/*/error_* "$NIGHT"/*/*/error_* 2> /dev/null | sed 's/^/error file: /'
} | tee "$NIGHT/summary.txt"
log "night finished in $(( SECONDS / 60 )) min: $NIGHT"
