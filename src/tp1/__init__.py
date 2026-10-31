from tp1.algorithms.a_star import a_star
from tp1.algorithms.greedy import greedy
from tp1.algorithms.iddfs import iddfs
from tp1.algorithms.dfs import dfs
from tp1.algorithms.bfs import bfs

import tp1.models.heuristics as h

from tp1.models.sokoban_parser import parse_board
from tp1.models.board_manager import BoardManager
from tp1.models.sokoban_board import SokobanBoard, path_to_movements

from tp1.types.heuristic import Heuristic
from tp1.types.sokoban_state import SokobanBoardState

import json
import sys
import time
from pathlib import Path
from typing import Callable, Sequence

heuristics = {
    "trivial": h.trivial,
    "closest": h.closest_goal_manhattan,
    "reduction": h.reduction_manhattan,
}

type SokobanBoardManager = BoardManager[SokobanBoardState, SokobanBoard]

# Imaging bringing the worst thing from Java into Python...
algorithms: dict[str,
    Callable[
        [SokobanBoardManager, SokobanBoardState, Heuristic],
        tuple[Sequence[SokobanBoardState] | None, int, int]
    ]
] = {
    "a_star": lambda m, s, h: a_star(m, s, h),
    "greedy": lambda m, s, h: greedy(m, s, h),
    "iddfs": lambda m, s, _: iddfs(m, s),
    "dfs": lambda m, s, _: dfs(m, s),
    "bfs": lambda m, s, _: bfs(m, s),
}

def main() -> None:
    global manager

    if len(sys.argv) < 3:
        print("Usage: tp1 <a_star|greedy|iddfs|dfs|bfs> [trivial*|closest|reduction] <board.json>")
        sys.exit(1)

    algorithm_name = sys.argv[1]
    if algorithm_name not in algorithms:
        print("Usage: tp1 <a_star|greedy|iddfs|dfs|bfs> [trivial*|closest|reduction] <board.json>")
        sys.exit(1)

    uses_h = algorithm_name in {"a_star", "greedy"}
    h_name = sys.argv[2] if uses_h and len(sys.argv) >= 4 else ""

    h_offset = 1 if h_name in heuristics else 0
    board_path = Path(sys.argv[2 + h_offset])

    board, start = parse_board(board_path)

    # print(f"Board {board.width}x{board.height}")
    # print(f"Player at {start[0]}")
    # print(f"Walls at {board.walls}")
    # print(f"Cubes at {start[1]}")
    # print(f"Goals at {board.wins}")

    print(f"Starting {algorithm_name}{f" ({h_name})" if uses_h else ""} in {board_path}")

    manager = BoardManager(board)

    algorithm = algorithms[algorithm_name]

    start_time = time.perf_counter()
    path, expanded, frontier = algorithm(manager, start, heuristics.get(h_name, h.trivial)(board))
    elapsed_time = time.perf_counter() - start_time

    # print(path)
    print("Solution found!" if path is not None else ":/")

    save_result(board_path, board, start, algorithm_name, h_name, path,expanded, frontier, elapsed_time)

def save_result(
    board_path: Path,
    board: SokobanBoard,
    start: SokobanBoardState,
    algorithm_name: str,
    h_name: str,
    path: Sequence[SokobanBoardState] | None,
    expanded: int,
    frontier: int,
    elapsed_time: float,
) -> None:
    board_data = {
        "x": board.width,
        "y": board.height,
        "player": list(start[0]),
        "walls": [list(coord) for coord in board.walls],
        "cubes": [list(coord) for coord in start[1]],
        "wins": [list(coord) for coord in board.wins],
    }

    output = {
        "algorithm": algorithm_name,
        "heuristic": h_name or None,
        "expanded_nodes": expanded,
        "frontier_nodes": frontier,
        "execution_time_seconds": elapsed_time,
        "board": board_data,
        "steps": [movement.name for movement in path_to_movements(path)] if path is not None else [],
    }

    output_dir = Path(__file__).resolve().parents[2] / "res" / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    suffix = f"_{h_name}" if h_name else ""
    output_path = output_dir / f"{board_path.stem}_{algorithm_name}{suffix}.json"

    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"Saved result to {output_path}")

if __name__ == "__main__":
    main()
