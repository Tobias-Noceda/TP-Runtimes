from typing import Sequence
from enum import Enum

from tp1.interfaces.board import Board

from tp1.types.coords import Coords
from tp1.types.sokoban_state import SokobanBoardState

class BoardCellType(Enum):
    WALL = 0
    GOAL = 1
    EMPTY = 2

class BoardMovement(Enum):
    UP = (0, -1)
    DOWN = (0, 1)
    LEFT = (-1, 0)
    RIGHT = (1, 0)

def path_to_movements(path: Sequence[SokobanBoardState]) -> list[BoardMovement]:
    movements: list[BoardMovement] = []

    for (prev_player, _), (next_player, _) in zip(path, path[1:]):
        delta = (next_player[0] - prev_player[0], next_player[1] - prev_player[1])
        movements.append(BoardMovement(delta))

    return movements

class BoardCell:
    def __init__(self, cell_type: BoardCellType):
        self.cell_type = cell_type

class SokobanBoard(Board[SokobanBoardState]):
    width: int
    height: int
    wins: Sequence[Coords]
    walls: Sequence[Coords]
    cells: list[list[BoardCell]]

    def __init__(self, width: int, height: int, walls: Sequence[Coords], wins: Sequence[Coords]):
        """
        Initializes a Board instance.
        width: The width of the board.
        height: The height of the board.
        elements: A list of tuples where each tuple contains the x-coordinate, y-coordinate, and the type of the cell (BoardCellType).
        elements should be only the non-moving elements (walls, goals, etc.). The player position is not included in this list.
        """
        self.width = width
        self.height = height

        self.wins = wins
        self.walls = walls

        self.cells = [[BoardCell(BoardCellType.EMPTY) for _ in range(width)] for _ in range(height)]

        for x, y in walls:
            self._set_cell(x, y, BoardCellType.WALL)

        for x, y in wins:
            self._set_cell(x, y, BoardCellType.GOAL)

    def _set_cell(self, x: int, y: int, cell_type: BoardCellType):
        if 0 <= x < self.width and 0 <= y < self.height:
            self.cells[y][x] = BoardCell(cell_type)
        else:
            raise ValueError("Coordinates out of bounds")

    def possible_movements(self, state: SokobanBoardState) -> Sequence[SokobanBoardState]:
        movements: list[SokobanBoardState] = []
        player_coords, box_coords = state

        for movement in BoardMovement:
            new_x = player_coords[0] + movement.value[0]
            new_y = player_coords[1] + movement.value[1]
            if self._is_out_of_bounds(new_x, new_y):
                continue
            if self._lands_in_wall(new_x, new_y):
                continue
            if (new_x, new_y) in box_coords:
                # If the player is trying to move into a box, check if the box can be pushed
                box_new_x = new_x + movement.value[0]
                box_new_y = new_y + movement.value[1]
                if self._is_out_of_bounds(box_new_x, box_new_y):
                    continue
                if self._lands_in_wall(box_new_x, box_new_y):
                    continue
                if (box_new_x, box_new_y) in box_coords:
                    continue  # Can't push a box into another box
                # Move the player and the box
                new_box_coords = tuple((box_new_x, box_new_y) if (x, y) == (new_x, new_y) else (x, y) for (x, y) in box_coords)
                movements.append(((new_x, new_y), new_box_coords))
            else:
                # Move the player only
                movements.append(((new_x, new_y), box_coords))

        return movements

    def _is_out_of_bounds(self, x: int, y: int) -> bool:
        return not (0 <= x < self.width and 0 <= y < self.height)

    def _lands_in_wall(self, x: int, y: int) -> bool:
        return self.cells[y][x].cell_type == BoardCellType.WALL

    def is_goal(self, state: SokobanBoardState) -> bool:
        _, box_coords = state
        for x, y in box_coords:
            if self.cells[y][x].cell_type != BoardCellType.GOAL:
                return False
        return True

    def _is_blocked(self, x: int, y: int):
        return self._is_out_of_bounds(x, y) or self._lands_in_wall(x, y)

    def _is_goal_cell(self, x: int, y: int):
        return self.cells[y][x].cell_type == BoardCellType.GOAL

    def _is_corner(self, x: int, y: int) -> bool:
        """A box against a wall on both axes at once can never be moved again."""
        vertical = self._is_blocked(x, y - 1) or self._is_blocked(x, y + 1)
        horizontal = self._is_blocked(x - 1, y) or self._is_blocked(x + 1, y)

        return vertical and horizontal

    def _is_wall_trapped(self, x: int, y: int) -> bool:
        return any(
            self._is_trapped_against(x, y, dx, dy)
            for dx, dy in (movement.value for movement in BoardMovement)
        )

    def _is_trapped_against(self, x: int, y: int, dx: int, dy: int) -> bool:
        """
        Checks the box at (x, y) against the wall in the (dx, dy) direction.

        A box with a wall above it can only slide sideways: pushing it down needs
        the player standing above, inside the wall, and pushing it up drives it
        into the wall. So it is stuck in its row, and it is dead if the stretch it
        can reach holds no goal.

        The catch is that the stretch ends where the wall ends: if the box can
        slide to a cell where the wall is gone, it recovers its vertical movement
        and escapes the row, so it is alive. Checking the whole row instead of the
        reachable stretch would report solvable states as dead.
        """
        if not self._is_blocked(x + dx, y + dy):
            return False

        # The box can only slide along the axis perpendicular to the wall
        slide_x, slide_y = dy, dx

        for step in (1, -1):
            reached_x, reached_y = x, y

            while True:
                if self._is_goal_cell(reached_x, reached_y):
                    return False  # Reachable goal, the box is still useful here
                if not self._is_blocked(reached_x + dx, reached_y + dy):
                    return False  # The wall ends, the box can escape the stretch

                next_x, next_y = reached_x + slide_x * step, reached_y + slide_y * step

                if self._is_blocked(next_x, next_y):
                    break  # Closed end, try the other direction

                reached_x, reached_y = next_x, next_y

        return True

    def dead_cells(self) -> frozenset[Coords]:
        """
        Cells where a box can never be pushed off again, so putting one there makes
        the level unsolvable. A state holding such a box has no solution, and every
        heuristic below reports infinity for it.

        Depends only on walls and goals, which are static, so it is computed once
        when the heuristic is built and then checked in O(1) per state.

        A goal is never dead: a box sitting on it is already where it belongs.

        The detection is deliberately asymmetric. A cell is only reported as dead
        when it is provably stuck, because a false positive would make the search
        report an unsolvable level, while a false negative only costs speed.
        """
        return frozenset(
            (x, y)
            for y in range(self.height)
            for x in range(self.width)
            if not self._is_blocked(x, y)
            and not self._is_goal_cell(x, y)
            and (self._is_corner(x, y) or self._is_wall_trapped(x, y))
        )
