# TP1 - Pathfinding algorithms

> [!NOTE]  
> Los comandos son relativos a la carpeta de este archivo (`/tp1`)

## Instalación

```bash
uv sync
```

## Uso

```bash
uv run tp1 a_star closest res/boards/board1.json
head -6 res/output/board1_a_star_closest.json
```

Algoritmos disponibles:
 - a_star
 - greedy
 - bfs
 - dfs
 - iddfs

Heurísticas disponibles (solo para `a_star` y `greedy`):
 - trivial
 - closest
 - reduction

Mapas disponibles en `res/boards/`

## Visualización

```bash
uv run python visualizer/visualizer.py res/output/board1_a_star_closest.json
```
