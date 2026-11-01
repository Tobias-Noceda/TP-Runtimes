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
    def __init__(self, sm: StateManager[S], start: S, h: Heuristic[S], num_workers: int = 4):
        self.sm = sm
        self.h = h

        self.counter = itertools.count()

        self.open_nodes: queue.PriorityQueue[MetaTuple[S]] = queue.PriorityQueue()
        self.submit(h(start), start, 0.0)

        self.previous_state: dict[S, S] = {}
        self.smallest_g_score: dict[S, float] = { start: 0.0 }
        self.solution: S | None = None

        self.workers: list[threading.Thread] = []

        for _ in range(num_workers):
            worker = threading.Thread(target=self._worker)
            worker.daemon = True
            worker.start()
            self.workers.append(worker)

    def submit(self, h: float, state: S, g_score: float):
        try:
            self.open_nodes.put((h, next(self.counter), state, g_score))
        except:
            pass

    def _worker(self):
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
                    continue

                if self.sm.is_goal(current):
                    self.solution = current
                    self.open_nodes.shutdown(True)
                    return

                for next in self.sm.next(current):
                    tentative = g_score + self.sm.dist(current, next)

                    if tentative < self.smallest_g_score.get(next, math.inf):
                        self.submit(tentative + self.h(next), next, tentative)
                        self.smallest_g_score[next] = tentative
                        self.previous_state[next] = current

            finally:
                self.open_nodes.task_done()

    def close(self):
        self.open_nodes.join()

        for worker in self.workers:
            worker.join()

        return (self.build_path(), 0, 0)

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
