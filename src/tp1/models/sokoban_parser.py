from typing import Any, Sequence

from tp1.models.sokoban_board import SokobanBoard

from tp1.types.coords import Coords
from tp1.types.sokoban_state import SokobanBoardState

import json
from pathlib import Path

def parse_board(path: str | Path) -> tuple[SokobanBoard, SokobanBoardState]:
    with open(path) as f:
        data = json.load(f)

    walls = __coords_tuple(data, "walls")
    wins = __coords_tuple(data, "wins")
    cubes = __coords_tuple(data, "cubes")
    player = tuple(data.get("player", (0, 0)))

    board = SokobanBoard(data["x"], data["y"], walls, wins)

    start = (player, cubes)

    return board, start

def __coords_tuple(data: Any, key: str) -> Sequence[Coords]:
    coords: list[Coords] = []
    for x, y in data.get(key, []):
        coords.append((x, y))

    return tuple(coords)
