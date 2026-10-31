from typing import Sequence

from tp1.interfaces.state_manager import StateManager
from tp1.interfaces.board import Board

# Board Node has a type (an enum with block, empty and goal) and a position (a tuple with x and y coordinates)
class BoardManager[S, B: Board](StateManager[S]):
    board: B

    def __init__(self, board: B):
        self.board = board

    def next(self, state: S) -> Sequence[S]:
        return self.board.possible_movements(state)

    def is_goal(self, state: S) -> bool:
        return self.board.is_goal(state)

    def dist(self, start: S, end: S) -> int:
        return 1
