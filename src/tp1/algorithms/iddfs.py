from typing import Sequence, Any

from tp1.interfaces.state_manager import StateManager

visited: dict[Any, int] = dict()
frontier = 1

# @link https://es.wikipedia.org/wiki/B%C3%BAsqueda_en_profundidad_iterativa
# @generic S The state type MUST be comparable and hashable
def iddfs[S](sm: StateManager[S], start: S, limit = 990) -> tuple[Sequence[S] | None, int, int]:
    for depth in range(limit):
        path, expanded, frontier = dls(sm, start, depth)
        if path is not None:
            return (path[::-1], expanded, frontier)

    return (None, len(visited), 0)

def dls[S](sm: StateManager[S], state: S, depth: int) -> tuple[list[S] | None, int, int]:
    global visited, frontier

    if visited.get(state, -1) > depth:
        return (None, 0, 0)

    visited[state] = depth

    if depth == 0:
        frontier -= 1
        frontier += len(sm.next(state))

        return ([state] if sm.is_goal(state) else None, len(visited), frontier)


    for next in sm.next(state):
        path, expanded, frontier = dls(sm, next, depth - 1)

        if path is not None:
            path.append(state)
            return (path, expanded, frontier)

    return (None, 0, 0)
