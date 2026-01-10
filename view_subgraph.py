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


def _scaled_positions(graph: nx.Graph):
    latitudes = np.array([graph.nodes[node]["latitude"] for node in graph.nodes])
    longitudes = np.array([graph.nodes[node]["longitude"] for node in graph.nodes])
    scale_factor = 1000
    return {
        node: ((lon - longitudes.min()) * scale_factor, (lat - latitudes.min()) * scale_factor)
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

    fig, ax = plt.subplots(figsize=(10, 8))
    positions = _scaled_positions(graph)

    nx.draw(
        graph,
        pos=positions,
        with_labels=True,
        node_size=260,
        node_color="#2ca02c",
        edge_color="#7f7f7f",
        width=0.8,
        font_size=8,
        ax=ax,
        connectionstyle="arc3,rad=0.1",
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
    plt.show()


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

    _print_stats(graph)
    plot_graph(graph, output_path)


if __name__ == "__main__":
    main()
