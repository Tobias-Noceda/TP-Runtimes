"""
Renders the JSON output of a `tp1` solver run (algorithm + board + steps) as
an animated GIF: walls, goals, the box(es) and the player moving step by step.

Usage:
    uv run --package tp1 python visualizer/visualizer.py <result.json> [-o output.gif]
"""

import argparse
import json
from pathlib import Path
from typing import Sequence

from PIL import Image, ImageDraw

from tp1.models.sokoban_board import BoardMovement

type SokobanState = tuple[tuple[int, int], Sequence[tuple[int, int]]]

CELL_SIZE = 64

FLOOR_COLOR = (238, 238, 238)
WALL_COLOR = (51, 51, 51)
GOAL_COLOR = (212, 175, 55)
BOX_COLOR = (176, 108, 48)
BOX_ON_GOAL_COLOR = (76, 175, 80)
PLAYER_COLOR = (47, 111, 237)
GRID_LINE_COLOR = (200, 200, 200)

def replay(player: tuple[int, int], boxes: Sequence[tuple[int, int]], steps: Sequence[str]) -> list[SokobanState]:
    """Re-derives every intermediate state from the initial position and the move names."""
    states: list[SokobanState] = [(player, tuple(boxes))]

    for step in steps:
        dx, dy = BoardMovement[step].value
        new_player = (player[0] + dx, player[1] + dy)

        if new_player in boxes:
            new_box = (new_player[0] + dx, new_player[1] + dy)
            boxes = tuple(new_box if box == new_player else box for box in boxes)

        player = new_player
        states.append((player, boxes))

    return states

def render_frame(
    width: int,
    height: int,
    walls: set[tuple[int, int]],
    goals: set[tuple[int, int]],
    state: SokobanState,
) -> Image.Image:
    player, boxes = state

    img = Image.new("RGB", (width * CELL_SIZE, height * CELL_SIZE), FLOOR_COLOR)
    draw = ImageDraw.Draw(img)

    for y in range(height):
        for x in range(width):
            x0, y0 = x * CELL_SIZE, y * CELL_SIZE
            x1, y1 = x0 + CELL_SIZE, y0 + CELL_SIZE

            if (x, y) in walls:
                draw.rectangle([x0, y0, x1, y1], fill=WALL_COLOR)
                continue

            draw.rectangle([x0, y0, x1, y1], outline=GRID_LINE_COLOR)

            if (x, y) in goals:
                margin = CELL_SIZE // 4
                draw.ellipse([x0 + margin, y0 + margin, x1 - margin, y1 - margin], outline=GOAL_COLOR, width=4)

    for box in boxes:
        x0, y0 = box[0] * CELL_SIZE, box[1] * CELL_SIZE
        margin = CELL_SIZE // 8
        color = BOX_ON_GOAL_COLOR if box in goals else BOX_COLOR
        draw.rounded_rectangle(
            [x0 + margin, y0 + margin, x0 + CELL_SIZE - margin, y0 + CELL_SIZE - margin],
            radius=8,
            fill=color,
        )

    px, py = player[0] * CELL_SIZE, player[1] * CELL_SIZE
    margin = CELL_SIZE // 6
    draw.ellipse([px + margin, py + margin, px + CELL_SIZE - margin, py + CELL_SIZE - margin], fill=PLAYER_COLOR)

    return img

def render_gif(data: dict, output_path: Path, duration_ms: int) -> None:
    board = data["board"]
    width, height = board["x"], board["y"]
    walls = {tuple(c) for c in board["walls"]}
    goals = {tuple(c) for c in board["wins"]}
    player = tuple(board["player"])
    boxes = [tuple(c) for c in board["cubes"]]

    states = replay(player, boxes, data["steps"])
    frames = [render_frame(width, height, walls, goals, state) for state in states]

    durations = [duration_ms] * len(frames)
    durations[-1] = duration_ms * 3  # hold on the final, solved frame

    frames[0].save(
        output_path,
        save_all=True,
        append_images=frames[1:],
        duration=durations,
        loop=0,
    )

def main() -> None:
    parser = argparse.ArgumentParser(description="Render a tp1 solver result as an animated GIF.")
    parser.add_argument("result", type=Path, help="Path to the solver's JSON output")
    parser.add_argument("-o", "--output", type=Path, default=None, help="Output GIF path (default: alongside the input file)")
    parser.add_argument("--duration", type=int, default=400, help="Milliseconds per frame")
    args = parser.parse_args()

    with open(args.result) as f:
        data = json.load(f)

    output_path = args.output or args.result.with_suffix(".gif")
    render_gif(data, output_path, args.duration)

    print(f"Saved animation to {output_path}")

if __name__ == "__main__":
    main()
