"""
Reads every solver result in res/output/ and renders, per board, a bar chart
 comparing algorithms (and heuristics): solution cost, expanded nodes and
 frontier nodes.

Usage:
    uv run --package tp1 python visualizer/compare.py [board_stem ...]
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt

INFORMED_ALGORITHMS = ["a_star", "greedy"]
UNINFORMED_ALGORITHMS = ["iddfs", "dfs", "bfs"]
# HEURISTICS = ["trivial", "closest", "reduction"]
HEURISTICS = ["closest", "reduction"]
ALGORITHMS = INFORMED_ALGORITHMS + UNINFORMED_ALGORITHMS
OUTPUT_DIR = Path(__file__).resolve().parents[1] / "res" / "output"

def parse_filename(path: Path) -> tuple[str, str, str | None] | None:
    """Splits `<board>_<algorithm>[_<heuristic>].json` into (board, algorithm, heuristic)."""
    stem = path.stem
    heuristic = None

    for candidate in HEURISTICS:
        suffix = f"_{candidate}"
        if stem.endswith(suffix):
            heuristic = candidate
            stem = stem[: -len(suffix)]
            break

    for algorithm in ALGORITHMS:
        if stem.endswith(f"_{algorithm}"):
            return stem[: -len(algorithm) - 1], algorithm, heuristic

    return None

def load_results(board_filter: set[str] | None) -> dict[str, dict[str, dict]]:
    """board -> series label -> result data"""
    results: dict[str, dict[str, dict]] = defaultdict(dict)

    for path in OUTPUT_DIR.glob("*.json"):
        parsed = parse_filename(path)
        if parsed is None:
            continue

        board, algorithm, heuristic = parsed
        if board_filter is not None and board not in board_filter:
            continue

        with open(path) as f:
            data = json.load(f)

        label = f"{algorithm} ({heuristic})" if heuristic else algorithm
        results[board][label] = data

    return results

def plot_board(board: str, algo_data: dict[str, dict], group: str) -> Path:
    labels = [label for label, _ in sorted(algo_data.items())]
    data_list = [data for _, data in sorted(algo_data.items())]

    fig, axes = plt.subplots(1, 3, figsize=(max(11, 1.2 * len(labels)), 4.5))
    fig.suptitle(f"Comparación de algoritmos {group} — {board}")

    costs = [len(data.get("steps") or []) for data in data_list]
    axes[0].bar(labels, costs, color="#3f51b5")
    axes[0].set_title("Costo de la solución (pasos)")

    expanded = [data.get("expanded_nodes") or 0 for data in data_list]
    axes[1].bar(labels, expanded, color="#ff9800")
    axes[1].set_title("Nodos expandidos")

    frontier = [data.get("frontier_nodes") or 0 for data in data_list]
    axes[2].bar(labels, frontier, color="#00acc1")
    axes[2].set_title("Nodos frontera")

    for ax in axes.flat:
        ax.tick_params(axis="x", rotation=30)
        for label in ax.get_xticklabels():
            label.set_ha("right")

    fig.tight_layout()

    output_path = OUTPUT_DIR / f"{board}_{group}_comparison.png"
    fig.savefig(output_path, dpi=150)
    plt.close(fig)

    return output_path

def plot_execution_times(board: str, algo_data: dict[str, dict]) -> Path:
    labels = list(algo_data)
    execution_times = [data.get("execution_time_seconds") or 0 for data in algo_data.values()]

    fig, ax = plt.subplots(figsize=(max(11, 1.2 * len(labels)), 4.5))
    fig.suptitle(f"Tiempos de ejecución de algoritmos — {board}")
    ax.bar(labels, execution_times, color="#4caf50")
    ax.set_ylabel("Tiempo de ejecución (segundos)")
    ax.set_title("Comparación de todos los métodos de búsqueda")
    ax.tick_params(axis="x", rotation=30)
    for label in ax.get_xticklabels():
        label.set_ha("right")

    fig.tight_layout()

    output_path = OUTPUT_DIR / f"{board}_execution_time_comparison.png"
    fig.savefig(output_path, dpi=150)
    plt.close(fig)

    return output_path

def main() -> None:
    board_filter = set(sys.argv[1:]) or None
    results = load_results(board_filter)

    if not results:
        print(f"No se encontraron resultados en {OUTPUT_DIR}")
        return

    for board, algo_data in sorted(results.items()):
        all_labels = [
            f"{algorithm} ({heuristic})"
            for algorithm in INFORMED_ALGORITHMS
            for heuristic in HEURISTICS
        ] + UNINFORMED_ALGORITHMS
        all_data = {label: algo_data.get(label, {}) for label in all_labels}
        output_path = plot_execution_times(board, all_data)
        print(f"{board}: gráfico de tiempos guardado en {output_path}")

        for group, algorithms in (
            ("informed", INFORMED_ALGORITHMS),
            ("uninformed", UNINFORMED_ALGORITHMS),
        ):
            group_data = {
                label: data
                for label, data in algo_data.items()
                if label.split(" (")[0] in algorithms
            }

            expected_labels = (
                [f"{algorithm} ({heuristic})" for algorithm in INFORMED_ALGORITHMS
                 for heuristic in HEURISTICS]
                if group == "informed"
                else UNINFORMED_ALGORITHMS
            )
            group_data = {label: group_data.get(label, {}) for label in expected_labels}
            if not group_data:
                continue

            output_path = plot_board(board, group_data, group)
            print(f"{board} ({group}): gráfico guardado en {output_path}")

if __name__ == "__main__":
    main()
