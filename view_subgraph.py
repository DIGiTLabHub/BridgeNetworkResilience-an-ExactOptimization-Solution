import argparse
import os
import pickle

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np


def _resolve_path(path: str, base_dir: str) -> str:
    if os.path.isabs(path):
        return path
    return os.path.join(base_dir, path)


def _split_nodes(graph: nx.Graph):
    depots = [node for node in graph.nodes if str(node).startswith("D")]
    bridges = [node for node in graph.nodes if str(node).startswith("B")]
    return depots, bridges


def _scaled_positions(graph: nx.Graph, target_width: float = 9.0, target_height: float = 6.0, pad: float = 0.5):
    latitudes = np.array([graph.nodes[node]["latitude"] for node in graph.nodes])
    longitudes = np.array([graph.nodes[node]["longitude"] for node in graph.nodes])

    min_lon = longitudes.min()
    max_lon = longitudes.max()
    min_lat = latitudes.min()
    max_lat = latitudes.max()

    dx = max(max_lon - min_lon, 1e-6)
    dy = max(max_lat - min_lat, 1e-6)

    usable_width = max(target_width - 2 * pad, 1e-3)
    usable_height = max(target_height - 2 * pad, 1e-3)
    scale = min(usable_width / dx, usable_height / dy)

    return {
        node: ((lon - min_lon) * scale + pad, (lat - min_lat) * scale + pad)
        for node, (lat, lon) in zip(graph.nodes, zip(latitudes, longitudes))
    }


def _print_stats(graph: nx.Graph):
    depots, bridges = _split_nodes(graph)
    total_distance = sum(data.get("highway_distance", 0) for _, _, data in graph.edges(data=True))
    total_km = total_distance / 1000
    total_miles = total_km * 0.621371

    print(f"Nodes: {graph.number_of_nodes()}")
    print(f"Edges: {graph.number_of_edges()}")
    print(f"Depots: {len(depots)}")
    print(f"Bridges: {len(bridges)}")
    print(f"Total Distance: {total_miles:.2f} miles ({total_km:.2f} km)")
    return {
        "nodes": graph.number_of_nodes(),
        "edges": graph.number_of_edges(),
        "depots": len(depots),
        "bridges": len(bridges),
        "total_distance_m": total_distance,
        "total_distance_km": total_km,
        "total_distance_miles": total_miles,
    }


def _compute_edge_curvatures(graph: nx.Graph):
    distances = [data.get("highway_distance", 0) for _, _, data in graph.edges(data=True)]
    if not distances:
        return {}

    min_distance = min(distances)
    max_distance = max(distances)

    if max_distance == min_distance:
        return {(u, v): 0.0 for u, v in graph.edges()}

    curvature_map = {}
    max_curvature = 0.15

    for u, v, data in graph.edges(data=True):
        dist = data.get("highway_distance", 0)
        if dist == min_distance:
            curvature = 0.0
        else:
            normalized_distance_ratio = (dist - min_distance) / (max_distance - min_distance)
            curvature = max_curvature * normalized_distance_ratio
        curvature_map[(u, v)] = curvature

    return curvature_map


def plot_graph(graph: nx.Graph, output_path: str):
    if graph.number_of_nodes() == 0:
        print("Empty graph. No plot generated.")
        return

    plt.rcParams.update({
        "figure.dpi": 300,
        "savefig.dpi": 300,
        "font.size": 10,
        "axes.titlesize": 12,
    })

    fig, ax = plt.subplots(figsize=(9, 6))
    positions = _scaled_positions(graph, target_width=9.0, target_height=6.0)
    curvature_map = _compute_edge_curvatures(graph)

    nx.draw_networkx_edges(
        graph,
        pos=positions,
        edge_color="#7f7f7f",
        width=0.8,
        ax=ax,
        arrows=True,
        connectionstyle=[f"arc3,rad={curvature_map.get((u, v), 0.0)}" for u, v in graph.edges()],
    )

    nx.draw_networkx_nodes(
        graph,
        pos=positions,
        node_size=260,
        node_color="#2ca02c",
        ax=ax,
    )

    nx.draw_networkx_labels(
        graph,
        pos=positions,
        font_size=8,
        ax=ax,
    )

    depots, bridges = _split_nodes(graph)
    if bridges:
        nx.draw_networkx_nodes(
            graph,
            pos=positions,
            nodelist=bridges,
            node_color="none",
            edgecolors="#2ca02c",
            node_size=260,
            linewidths=1.2,
            ax=ax,
        )

    if depots:
        nx.draw_networkx_nodes(
            graph,
            pos=positions,
            nodelist=depots,
            node_color="#d62728",
            node_size=300,
            ax=ax,
        )

    plt.title("Bridge Subgraph")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    plt.savefig(output_path, format="pdf", bbox_inches="tight")
    plt.close()


def _write_markdown(graph: nx.Graph, stats: dict, output_path: str):
    base_name = os.path.splitext(output_path)[0]
    md_path = f"{base_name}.md"

    depots, bridges = _split_nodes(graph)

    edge_list = sorted(
        [(u, v, data.get("highway_distance", 0)) for u, v, data in graph.edges(data=True)],
        key=lambda x: x[2]
    )

    distances = [dist for _, _, dist in edge_list]
    min_dist = min(distances) if distances else 0.0
    max_dist = max(distances) if distances else 0.0
    avg_dist = sum(distances) / len(distances) if distances else 0.0

    with open(md_path, "w") as f:
        f.write("# Bridge Subgraph Statistics\n\n")
        f.write("## Summary\n\n")
        f.write(f"- **Nodes:** {stats['nodes']}\n")
        f.write(f"- **Edges:** {stats['edges']}\n")
        f.write(f"- **Depots:** {stats['depots']}\n")
        f.write(f"- **Bridges:** {stats['bridges']}\n")
        f.write(f"- **Total Distance:** {stats['total_distance_miles']:.2f} miles ({stats['total_distance_km']:.2f} km)\n")
        f.write(f"- **Min Edge Distance:** {min_dist / 1000:.2f} km ({min_dist / 1000 * 0.621371:.2f} miles)\n")
        f.write(f"- **Avg Edge Distance:** {avg_dist / 1000:.2f} km ({avg_dist / 1000 * 0.621371:.2f} miles)\n")
        f.write(f"- **Max Edge Distance:** {max_dist / 1000:.2f} km ({max_dist / 1000 * 0.621371:.2f} miles)\n\n")

        f.write("## Edge Distances\n\n")
        f.write("| Edge | Distance (km) | Distance (miles) |\n")
        f.write("|------|---------------|------------------|\n")

        for u, v, dist_m in edge_list:
            dist_km = dist_m / 1000
            dist_miles = dist_km * 0.621371
            f.write(f"| {u}-{v} | {dist_km:.2f} | {dist_miles:.2f} |\n")

    print(f"Markdown table saved to: {md_path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pkl", default="Sample-Subgraphs/bridge_subgraph_001.pkl")
    parser.add_argument("--output", default="Plots/subgraph-view.pdf")
    args = parser.parse_args()

    base_dir = os.path.dirname(os.path.abspath(__file__))
    pkl_path = _resolve_path(args.pkl, base_dir)
    output_path = _resolve_path(args.output, base_dir)

    with open(pkl_path, "rb") as handle:
        graph = pickle.load(handle)

    stats = _print_stats(graph)
    plot_graph(graph, output_path)
    _write_markdown(graph, stats, output_path)


if __name__ == "__main__":
    main()
