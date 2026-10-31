# Typings
from typing import Callable

type Heuristic[S] = Callable[[S], float]
