# TP1 — Motor de búsqueda para Sokoban

## Enunciado

Implementar un motor de búsqueda de soluciones para el juego **Sokoban**.

El sistema recibe un tablero, busca una solución con el algoritmo **A\*** usando una heurística bien definida, y produce la **secuencia de pasos** que resuelve el nivel.

Escrito en Python.

## Requisitos

- Parser de tableros desde **JSON**. El formato ya está definido; es modificable si el modelado lo pide.
- Algoritmo **A\*** sobre el espacio de estados del Sokoban.
- Al menos una **heurística** bien definida y justificada (admisible si se quiere garantizar optimalidad).
- Salida: secuencia de movimientos que lleva del estado inicial a un estado solución.

## Modelado

Reglas del Sokoban a respetar en el modelado:

- Grilla 2D con paredes, pisos, cajas, objetivos (*goals*) y un jugador.
- El jugador se mueve en 4 direcciones (arriba/abajo/izquierda/derecha).
- Mover contra una caja la **empuja** una celda en la misma dirección, solo si la celda destino de la caja está libre (ni pared ni otra caja).
- **Estado objetivo:** toda caja sobre un objetivo.

## Formato JSON

`res/boards/board1.json`. Coordenadas `[x, y]`, origen arriba-izquierda:

```json
{
  "x": 5,
  "y": 5,
  "player": [2, 2],
  "walls":  [[0, 0], [1, 1], [3, 3], [4, 4]],
  "cubes":  [[1, 2]],
  "wins":   [[2, 2]]
}
```

`x`/`y` son ancho y alto. `cubes` = cajas, `wins` = objetivos. El parser vive en `src/tp1/__init__.py:parse_board`.

## Arquitectura

```
src/tp1/
├── __init__.py              # parse_board + main (entrypoint `tp1 <board.json>`)
├── interfaces/
│   ├── board.py             # Board[S]: possible_movements(state), is_goal(state)
│   └── state_manager.py     # StateManager[S]: next(state), dist(a, b), is_goal(state)
├── types/
│   ├── coords.py            # type Coords = Tuple[int, int]
│   ├── heuristic.py         # type Heuristic[S] = Callable[[S], int]
│   └── sokoban_state.py     # type SokobanBoardState = Tuple[Coords, Sequence[Coords]]
├── models/
│   ├── board_manager.py     # BoardManager[S, B: Board]: adapta un Board a StateManager
│   └── sokoban_board.py     # SokobanBoard(Board[SokobanBoardState]) + BoardCellType/BoardCell/BoardMovement
└── algorithms/
    ├── a_star.py            # a_star(sm, start, h) -> Sequence[S] | None
    └── iddfs.py             # iddfs(sm, start, limit) -> Sequence[S] | None
```

## Decisiones de diseño

- **El estado no es una clase.** `SokobanBoardState = (player_coords, box_coords)`, una tupla de tuplas → hashable y comparable sin escribir `__hash__`/`__eq__`. Las paredes y objetivos son estáticos y viven en `SokobanBoard`, fuera del estado.
- **Dos interfaces, no una.** `StateManager[S]` es lo único que ven los algoritmos (`next`/`dist`/`is_goal`). `Board[S]` es el modelo del problema. `BoardManager` adapta uno al otro y fija `dist == 1` (costo uniforme por movimiento).
- **Los algoritmos son genéricos en `S`.** `a_star` e `iddfs` no importan nada de Sokoban; reutilizables en otros TPs.
- **Sin clase `Metadata`.** `a_star` guarda `g_score` en la tupla del heap y en `smallest_g_score: dict[S, float]`; el heap usa `(f_score, counter, state, g_score)` con `counter` como desempate para no comparar estados.
- **Heurística fuera del algoritmo,** pasada como `Heuristic[S]`. Las heurísticas concretas viven en `SokobanBoard` (commit "Moved heuristic to board").

## Estado del código

- `a_star` e `iddfs` implementados y funcionando.
- Parser JSON, `SokobanBoard`, `BoardManager` y entrypoint listos.
- **Única heurística: `SokobanBoard.h_trivial`** (0 si goal, 1 si no) → A\* degenera en Dijkstra. Falta la heurística real del enunciado: Manhattan cajas↔objetivos (suma, o *matching* mínimo). Documentar admisibilidad.
- **Falta detección de deadlocks** (caja en esquina, contra pared sin objetivo en esa línea). Podarlos acelera mucho la búsqueda.
- `main` tiene la llamada a `a_star` comentada y usa `iddfs`. Volver a A\* cuando haya heurística real.
- `iddfs.dls` usa un `global max_depth` para debug printing y recursión sin límite explícito de stack — sacar/limpiar antes de entregar.
- La salida es la secuencia de **estados**, no de movimientos. El enunciado pide movimientos: falta traducir estados consecutivos a `BoardMovement`.
- `numpy` está declarado como dependencia en `pyproject.toml` pero no se usa todavía.
