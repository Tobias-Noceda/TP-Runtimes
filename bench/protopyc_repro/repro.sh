#!/usr/bin/env bash
# Reproduces the protopyc bugs found on 2026-11-02 (tp1 compile attempt).
# Builds each module twice (default link, and -Wl,-Bsymbolic) and runs main.py
# against the compiled modules. Writes everything to stdout.
#   bench/protopyc_repro/repro.sh [work dir]
set -uo pipefail
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PROTO=${PROTO:-$HERE/../../../protoPython/build_release}
PROTOPYC=$PROTO/src/compiler/protopyc
PROTOPY=$PROTO/src/runtime/protopy
WORK=${1:-$(mktemp -d)}

for variant in default bsymbolic; do
    out=$WORK/$variant
    mkdir -p "$out"
    cp "$HERE/main.py" "$out/"
    for m in mod_a mod_b pep695 generic_base builtin_generic; do
        b=$WORK/build_${variant}_$m
        mkdir -p "$b" && cp "$HERE/$m.py" "$b/"
        (cd "$b" && "$PROTOPYC" "$m.py" --emit-make > build.log 2>&1 &&
            { [[ $variant == default ]] || sed -i 's|^LDFLAGS\s*=|LDFLAGS = -Wl,-Bsymbolic|' Makefile; } &&
            make -s >> build.log 2>&1 && cp module.so "$out/$m.so") || { echo "build $variant/$m FAILED:"; tail -5 "$b/build.log"; }
    done
    echo "== link: $variant"
    echo "exported symbols defined by both mod_a.so and mod_b.so:"
    comm -12 <(nm -D --defined-only "$out/mod_a.so" | awk '{print $3}' | grep py_func | sort) \
             <(nm -D --defined-only "$out/mod_b.so" | awk '{print $3}' | grep py_func | sort) | sed 's/^/  /'
    for case in clash pep695 generic_base builtin_generic; do
        result=$(cd "$out" && timeout 60 "$PROTOPY" -p "$out" main.py "$case" 2>&1 | grep -E ' ok:|Error' | tail -1)
        echo "  $case: $result"
    done
done
echo "== CPython (reference)"
for case in clash pep695 generic_base builtin_generic; do
    echo "  $case: $(cd "$HERE" && python3.14 main.py "$case" 2>&1 | tail -1)"
done
echo "== interpreted protopy (reference)"
for case in clash pep695 generic_base builtin_generic; do
    echo "  $case: $(cd "$HERE" && timeout 60 "$PROTOPY" -p "$HERE" main.py "$case" 2>&1 | grep -E ' ok:|Error' | tail -1)"
done
