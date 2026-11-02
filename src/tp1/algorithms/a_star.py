# Utils
import math

# Data structures
import queue
import threading
import itertools

# Typings
from tp1.types.heuristic import Heuristic
from tp1.interfaces.state_manager import StateManager

type MetaTuple[S] = tuple[float, int, S, float]

class AStar[S]:
    # Number of stripes when locks=True: a state's stripe is hash(state) & mask.
    LOCK_STRIPES = 64

    def __init__(self, sm: StateManager[S], start: S, h: Heuristic[S], num_workers: int = 4,
                 locks: bool = False):
        self.sm = sm
        self.h = h

        # locks=False keeps the original lock-free update, with its
        # check-then-act race (counted in `regressions`). locks=True makes the
        # check and both writes one critical section per state, through striped
        # locks so that unrelated states rarely contend.
        self.locks: list[threading.Lock] | None = (
            [threading.Lock() for _ in range(self.LOCK_STRIPES)] if locks else None
        )

        self.counter = itertools.count()

        self.open_nodes: queue.PriorityQueue[MetaTuple[S]] = queue.PriorityQueue()
        self.submit(h(start), start, 0.0)

        self.previous_state: dict[S, S] = {}
        self.smallest_g_score: dict[S, float] = { start: 0.0 }
        self.solution: S | None = None
        self.frontier = 0

        self.workers: list[threading.Thread] = []
        # One slot per worker, written once when it exits, so counting adds no
        # shared writes: (expanded, stale, regressions).
        self.stats: list[tuple[int, int, int]] = [(0, 0, 0)] * num_workers

        for i in range(num_workers):
            worker = threading.Thread(target=self._worker, args=(i,))
            worker.daemon = True
            worker.start()
            self.workers.append(worker)

    def submit(self, h: float, state: S, g_score: float):
        try:
            self.open_nodes.put((h, next(self.counter), state, g_score))
        except:
            pass

    def _worker(self, index: int):
        expanded = 0     # nodes whose successors were generated
        stale = 0        # popped entries already superseded by a cheaper path
        regressions = 0  # writes that replaced a g-score as good or better,
                         # stored by another thread between our check and our
                         # write: a lost update (check-then-act race)
        try:
            while True:
                if self.solution is not None:
                    return

                try:
                    task = self.open_nodes.get()
                except:
                    return

                try:
                    _, _, current, g_score = task

                    if current is None:
                        return

                    if self.smallest_g_score.get(current, math.inf) < g_score:
                        stale += 1
                        continue

                    if self.sm.is_goal(current):
                        self.solution = current
                        # Read before shutdown(True), which empties the queue.
                        self.frontier = self.open_nodes.qsize()
                        self.open_nodes.shutdown(True)
                        return

                    expanded += 1
                    for next in self.sm.next(current):
                        tentative = g_score + self.sm.dist(current, next)

                        if self.locks is not None:
                            with self.locks[hash(next) & (self.LOCK_STRIPES - 1)]:
                                improved = tentative < self.smallest_g_score.get(next, math.inf)
                                if improved:
                                    self.smallest_g_score[next] = tentative
                                    self.previous_state[next] = current
                            # Outside the stripe lock: submit() takes the queue's
                            # own lock, which need not be nested in ours.
                            if improved:
                                self.submit(tentative + self.h(next), next, tentative)

                        elif tentative < self.smallest_g_score.get(next, math.inf):
                            self.submit(tentative + self.h(next), next, tentative)
                            if self.smallest_g_score.get(next, math.inf) <= tentative:
                                regressions += 1
                            self.smallest_g_score[next] = tentative
                            self.previous_state[next] = current

                finally:
                    self.open_nodes.task_done()
        finally:
            self.stats[index] = (expanded, stale, regressions)

    def close(self):
        self.open_nodes.join()

        if self.solution is None:
            # The frontier ran dry without a goal: every worker is blocked in
            # get(). Shutting the queue down wakes them with ShutDown.
            self.open_nodes.shutdown(True)

        for worker in self.workers:
            worker.join()

        self.expanded = sum(s[0] for s in self.stats)
        self.stale = sum(s[1] for s in self.stats)
        self.regressions = sum(s[2] for s in self.stats)
        return (self.build_path(), self.expanded, self.frontier)

    def build_path(self):
        if self.solution is None:
            return None

        current = self.solution

        total_path: list[S] = [current]
        while current in self.previous_state:
            current = self.previous_state[current]
            total_path.append(current)

        total_path.reverse()
        return total_path
