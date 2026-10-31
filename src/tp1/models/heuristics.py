import math
# from itertools import permutations  # only used by matching_manhattan, below
from typing import Sequence

from tp1.models.sokoban_board import SokobanBoard

from tp1.types.coords import Coords
from tp1.types.heuristic import Heuristic
from tp1.types.sokoban_state import SokobanBoardState

def trivial(board: SokobanBoard) -> Heuristic[SokobanBoardState]:
    def h(state: SokobanBoardState) -> int:
        return 0 if board.is_goal(state) else 1

    return h

def manhattan(a: Coords, b: Coords) -> int:
    # @link https://en.wikipedia.org/wiki/Taxicab_geometry
    return abs(a[0] - b[0]) + abs(a[1] - b[1])

def closest_goal_manhattan(board: SokobanBoard) -> Heuristic[SokobanBoardState]:
    goals: Sequence[Coords] = board.wins
    dead: frozenset[Coords] = board.dead_cells()

    if not goals:
        raise ValueError("The board has no goals")

    def h(state: SokobanBoardState) -> float:
        _, boxes = state

        if any(box in dead for box in boxes):
            return math.inf

        return sum(min(manhattan(box, goal) for goal in goals) for box in boxes)

    return h

def reduction_manhattan(board: SokobanBoard) -> Heuristic[SokobanBoardState]:
    goals: Sequence[Coords] = board.wins
    dead: frozenset[Coords] = board.dead_cells()

    if not goals:
        raise ValueError("The board has no goals")

    cache: dict[Sequence[Coords], float] = {}

    def h(state: SokobanBoardState) -> float:
        _, boxes = state

        if boxes in cache:
            return cache[boxes]

        if len(boxes) != len(goals):
            raise ValueError(
                f"The board has {len(boxes)} boxes and {len(goals)} goals; "
                "this heuristic is only admissible when they match"
            )

        if any(box in dead for box in boxes):
            cache[boxes] = math.inf
            return math.inf

        # Matriz de costos de cada box a cada goal
        full_costs = [[manhattan(box, goal) for goal in goals] for box in boxes]

        # Agarro el minimo de cada fila
        row_mins = [min(row) for row in full_costs]

        # Resto el minimo de cada fila a cada elemento de la fila
        reduced = [[cost - min for cost in row] for row, min in zip(full_costs, row_mins)]

        # Busco el minimo de la columna de cada goal en la matriz ya reducida
        cols = [min(row[goal] for row in reduced) for goal in range(len(goals))]

        # Sumo los minimos de cada fila y los minimos de cada columna para obtener la cota inferior
        best: float = sum(row_mins) + sum(cols)

        cache[boxes] = best

        return best

    return h

# def matching_manhattan(board: SokobanBoard) -> Heuristic[SokobanBoardState]:
#     """
#     Minimum cost assignment of boxes to goals, using Manhattan as the cost of
#     moving a box to a goal. Every box gets a different goal.
#
#     Admissible: the real solution ends with every box on a different goal, which
#     is one particular assignment, and its real cost is at least the sum of the
#     Manhattan distances it implies. Taking the minimum over every assignment can
#     only lower that bound, so the estimate never overestimates.
#
#     Dominates closest_goal_manhattan (which is this without the "different goal"
#     restriction), so it never expands more nodes than it does.
#
#     Solved by brute force over every injective assignment of boxes to goals:
#     O(goals! / (goals - boxes)!) per box layout. Fine for the handful of boxes
#     of this TP; a bitmask DP over the subsets of goals would bring it down to
#     O(2^goals * goals) if the boards ever grow.
#
#     The estimate only depends on the boxes, not on the player, and the search
#     visits the same box layout with many different player positions, so results
#     are memoized by box layout.
#     """
#     goals: Sequence[Coords] = board.wins
#     dead: frozenset[Coords] = board.dead_cells()
#
#     if not goals:
#         raise ValueError("The board has no goals")
#
#     cache: dict[Sequence[Coords], float] = {}
#
#     def h(state: SokobanBoardState) -> float:
#         _, boxes = state
#
#         if boxes in cache:
#             return cache[boxes]
#
#         if any(box in dead for box in boxes):
#             cache[boxes] = math.inf
#             return math.inf
#
#         # Every way of giving each box a different goal; the cheapest one is the
#         # bound. Empty when there are more boxes than goals: unsolvable, so inf.
#         best: float = min(
#             (
#                 sum(manhattan(box, goal) for box, goal in zip(boxes, assignment))
#                 for assignment in permutations(goals, len(boxes))
#             ),
#             default=math.inf,
#         )
#
#         cache[boxes] = best
#
#         return best
#
#     return h
