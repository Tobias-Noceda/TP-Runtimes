from abc import ABC, abstractmethod
from typing import Sequence

class Board[S](ABC):
    @abstractmethod
    def possible_movements(self, state: S) -> Sequence[S]:
        """
        Returns a sequence of possible movements from the given state.
        This method should be overridden in subclasses to provide specific movement logic.
        """
        pass

    @abstractmethod
    def is_goal(self, state: S) -> bool:
        """
        Checks if the given state is a goal state.
        This method should be overridden in subclasses to provide specific goal-checking logic.
        """
        pass
