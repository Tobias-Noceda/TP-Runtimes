# Utils
import math

# Data structures
from heapq import heappush, heappop
from collections import deque

# Typings
from typing import Sequence
from tp1.types.heuristic import Heuristic
from tp1.interfaces.state_manager import StateManager

type MetaTuple[S] = tuple[float, int, S, float]

# @link https://en.wikipedia.org/wiki/A*_search_algorithm
# @generic S The state type MUST be comparable and hashable
def a_star[S](sm: StateManager[S], start: S, h: Heuristic[S]) -> tuple[Sequence[S] | None, int, int]:
    counter: int = 0
    open_nodes: list[MetaTuple[S]] = [(h(start), counter, start, 0.0)]
    closed_nodes = 0

    smallest_g_score: dict[S, float] = { start: 0.0 }

    previous_state: dict[S, S] = {}

    while open_nodes:
        peak: MetaTuple[S] = heappop(open_nodes)
        _, _, current, g_score = peak

        if smallest_g_score.get(current, math.inf) < g_score:
            continue

        closed_nodes += 1
        if sm.is_goal(current):
            path = build_path(previous_state, current)
            # Filter old inneficient states
            open = len([n for n in open_nodes if smallest_g_score.get(current, math.inf) >= g_score])
            return (path, closed_nodes, open)

        for next in sm.next(current):
            tentative: float = g_score + sm.dist(current, next)

            if tentative < smallest_g_score.get(next, math.inf):
                counter += 1
                update: MetaTuple[S] = (tentative + h(next), counter, next, tentative)

                heappush(open_nodes, update)
                smallest_g_score[next] = tentative
                previous_state[next] = current

    return (None, closed_nodes, 0)

def build_path[S](came_from: dict[S, S], current: S) -> Sequence[S]:
    total_path = deque([current])

    while current in came_from:
        current = came_from[current]
        total_path.appendleft(current)

    return list(total_path)
