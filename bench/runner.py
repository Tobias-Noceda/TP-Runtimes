# One benchmark sample: solve one board once and print one JSON line.
# Runs under every runtime being compared (CPython, CPython 3.14t, protopy),
# so it only uses the standard library and tp1 itself.
#
# Usage: runner.py <board.json> <algorithm> <heuristic> <workers>

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import tp1.models.heuristics as h
from tp1.algorithms.a_star import AStar
from tp1.algorithms.bfs import bfs
from tp1.algorithms.greedy import greedy
from tp1.models.board_manager import BoardManager
from tp1.models.sokoban_parser import parse_board

heuristics = {
    "trivial": h.trivial,
    "closest": h.closest_goal_manhattan,
    "reduction": h.reduction_manhattan,
}


def main() -> None:
    board_path, algorithm, h_name, workers = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])

    board, start = parse_board(board_path)
    manager = BoardManager(board)
    heuristic = heuristics[h_name](board)

    started = time.perf_counter()
    if algorithm == "a_star":
        path, _, _ = AStar(manager, start, heuristic, num_workers=workers).close()
    elif algorithm == "greedy":
        path, _, _ = greedy(manager, start, heuristic)
    elif algorithm == "bfs":
        path, _, _ = bfs(manager, start)
    else:
        raise SystemExit(f"unknown algorithm {algorithm}")
    elapsed = time.perf_counter() - started

    print(json.dumps({
        "seconds": elapsed,
        "solved": path is not None,
        "steps": len(path) - 1 if path is not None else None,
    }))


if __name__ == "__main__":
    main()
