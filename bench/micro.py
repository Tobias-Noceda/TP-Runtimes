# Microbenchmarks of the operations tp1's A* leans on, one JSON line per test:
# {"test", "ns_per_op", "ops", "runtime"}. Best of REPS runs, single thread.
# Runs unchanged on CPython, CPython 3.14t and protopy (standard library only).
#
# Usage: micro.py [ops per test, default 20000] [reps, default 3]
import heapq
import json
import queue
import sys
import threading
import time
from collections import deque
from enum import Enum

N = int(sys.argv[1]) if len(sys.argv) > 1 else 20000
REPS = int(sys.argv[2]) if len(sys.argv) > 2 else 3


class Move(Enum):
    UP = (0, -1)
    DOWN = (0, 1)
    LEFT = (-1, 0)
    RIGHT = (1, 0)


STATE = ((3, 4), ((1, 2), (5, 6), (7, 8)))  # (player, boxes): tp1's state shape


def t_int_loop(n):
    x = 0
    for i in range(n):
        x += i
    return x


def t_call(n):
    def f(a):
        return a
    for i in range(n):
        f(i)


def t_tuple_index(n):
    t = STATE
    for _ in range(n):
        t[0]
        t[1]


def t_tuple_build(n):
    for i in range(n):
        (i, i + 1)


def t_tuple_genexpr(n):
    boxes = STATE[1]
    for _ in range(n // 4):
        tuple(b for b in boxes)


def t_enum_iter(n):
    for _ in range(n // 4):
        for m in Move:
            m.value


def t_hash_nested_tuple(n):
    for i in range(n):
        hash(((i, 1), ((2, 3), (4, 5))))


def t_dict_set_get_tuple_key(n):
    d = {}
    for i in range(n):
        k = ((i, 1), ((2, 3), (4, 5)))
        d[k] = i
        d.get(k)


def t_set_add_contains(n):
    s = set()
    for i in range(n):
        s.add((i, i))
        (i, i) in s


def t_heappush_pop(n):
    h = []
    for i in range(n):
        heapq.heappush(h, (n - i, i))
    for _ in range(n):
        heapq.heappop(h)


def t_deque(n):
    d = deque()
    for i in range(n):
        d.append(i)
    for _ in range(n):
        d.popleft()


def t_lock(n):
    lock = threading.Lock()
    for _ in range(n):
        with lock:
            pass


def t_priority_queue(n):
    q = queue.PriorityQueue()
    for i in range(n // 4):
        q.put((n - i, i))
    for _ in range(n // 4):
        q.get()
        q.task_done()


TESTS = [
    ("int_loop", t_int_loop, 1),
    ("call", t_call, 1),
    ("tuple_index_x2", t_tuple_index, 1),
    ("tuple_build", t_tuple_build, 1),
    ("tuple_genexpr_3", t_tuple_genexpr, 4),
    ("enum_iter_4", t_enum_iter, 4),
    ("hash_nested_tuple", t_hash_nested_tuple, 1),
    ("dict_set_get_tuple_key", t_dict_set_get_tuple_key, 1),
    ("set_add_contains", t_set_add_contains, 1),
    ("heappush_pop", t_heappush_pop, 1),
    ("deque_append_popleft", t_deque, 1),
    ("lock_acquire_release", t_lock, 1),
    ("priority_queue_put_get", t_priority_queue, 4),
]

runtime = f"{sys.implementation.name} {sys.version.split()[0]} gil={getattr(sys, '_is_gil_enabled', lambda: True)()}"
only = set(sys.argv[3].split(",")) if len(sys.argv) > 3 else None
for name, fn, divisor in TESTS:
    if only and name not in only:
        continue
    best = float("inf")
    for _ in range(REPS):
        started = time.perf_counter()
        fn(N)
        best = min(best, time.perf_counter() - started)
    ops = N // divisor
    print(json.dumps({"test": name, "ns_per_op": best / ops * 1e9, "ops": ops, "runtime": runtime}), flush=True)
