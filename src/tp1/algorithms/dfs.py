from typing import Sequence

from tp1.interfaces.state_manager import StateManager

visited = set()
expanded = 0
frontier = 1

# https://en.wikipedia.org/wiki/Depth-first_search
def dfs[S](sm: StateManager[S], state: S) -> tuple[Sequence[S] | None, int, int]:
    path, expanded, frontier = _dfs(sm, state)
    return (path[::-1] if path is not None else None, expanded, frontier)

def _dfs[S](sm: StateManager[S], state: S) -> tuple[list[S] | None, int, int]:
    global expanded, frontier

    frontier -= 1
    expanded += 1
    if sm.is_goal(state):
        return ([state], expanded, frontier)

    visited.add(state)

    childs = set(sm.next(state)) - visited
    frontier += len(childs)

    for next in childs:
        try:
            result = _dfs(sm, next)
        except:
            result = (None, 0, 0)

        if result[0] is not None:
            result[0].append(state)
            return result

    return (None, expanded, 0)
