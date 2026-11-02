# Lost-update check on the runtime's own containers, no locks anywhere.
#  1. dict/set/list: each thread adds its OWN distinct keys -> nothing may be lost
#     if each single operation is atomic (protopy: CAS on an immutable snapshot).
#  2. d[k] += 1 on ONE shared key: read + write are two operations -> updates
#     are expected to be lost without a GIL (check-then-act, same as A*).
# Usage: <python> lostwrites.py [threads] [ops_per_thread]
import sys
import threading
import time

T = int(sys.argv[1]) if len(sys.argv) > 1 else 8
N = int(sys.argv[2]) if len(sys.argv) > 2 else 5000

shared_dict = {}
shared_set = set()
shared_list = []
counter = {"k": 0}
barrier = threading.Barrier(T)


def distinct(tid):
    barrier.wait()
    base = tid * N
    for i in range(base, base + N):
        shared_dict[i] = tid
        shared_set.add(i)
        shared_list.append(i)


def increment(_tid):
    barrier.wait()
    for _ in range(N):
        counter["k"] += 1


def run(target):
    threads = [threading.Thread(target=target, args=(t,)) for t in range(T)]
    started = time.perf_counter()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return time.perf_counter() - started


gil = getattr(sys, "_is_gil_enabled", lambda: True)()
print(f"runtime: {sys.version.split()[0]} gil={gil}  threads={T} ops/thread={N}")

t1 = run(distinct)
expected = T * N
print(f"distinct keys  dict {len(shared_dict)}/{expected} lost {expected - len(shared_dict)}"
      f" | set {len(shared_set)}/{expected} lost {expected - len(shared_set)}"
      f" | list {len(shared_list)}/{expected} lost {expected - len(shared_list)}  ({t1:.2f}s)")

barrier = threading.Barrier(T)
t2 = run(increment)
print(f"d[k] += 1      {counter['k']}/{expected} lost {expected - counter['k']}"
      f" ({100 * (expected - counter['k']) / expected:.1f}%)  ({t2:.2f}s)")
