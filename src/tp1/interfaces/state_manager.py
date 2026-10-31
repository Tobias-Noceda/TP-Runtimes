from abc import ABC, abstractmethod
from typing import Sequence

class StateManager[S](ABC):
    @abstractmethod
    def next(self, state: S) -> Sequence[S]: pass

    @abstractmethod
    def dist(self, start: S, end: S) -> int: pass

    @abstractmethod
    def is_goal(self, state: S) -> bool: pass
