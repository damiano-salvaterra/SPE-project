from itertools import combinations

import pandas as pd
import numpy as np
import networkx as nx


def build_connectivity_graph(
    repetition: "RepetitionResults", timestamp: int
) -> nx.Graph:

    G = nx.Graph()

    # Filter to specific timestamp window
    window = repetition.neighbor_df[
        (repetition.neighbor_df["timestamp"] >= timestamp - 5)
        & (repetition.neighbor_df["timestamp"] <= timestamp + 5)
    ]

    for _, row in window.iterrows():
        # Add bidirectional edge if they're neighbors
        if row["type"] in [
            "NODE_NEIGHBOR",
            "NODE_PARENT",
            "NODE_CHILD",
        ]:
            G.add_edge(row["node_id"], row["neighbor"])

    for node in repetition.positions_df["node_id"].unique():
        if node not in G:
            G.add_node(node)

    return G


def build_tree_topology(repetition: "RepetitionResults", timestamp: int) -> nx.DiGraph:

    G = nx.DiGraph()

    # Filter to specific timestamp window
    window = repetition.neighbor_df[
        (repetition.neighbor_df["timestamp"] >= timestamp - 5)
        & (repetition.neighbor_df["timestamp"] <= timestamp + 5)
    ]

    for _, row in window.iterrows():
        if row["type"] == "NODE_PARENT":
            G.add_edge(row["neighbor"], row["node_id"])
        elif row["type"] == "NODE_CHILD":
            G.add_edge(row["node_id"], row["neighbor"])

    for node in repetition.positions_df["node_id"].unique():
        if node not in G:
            G.add_node(node)

    return G


def pairwise_shortest_paths(
    connectivity_graph: nx.Graph, tree: nx.DiGraph
) -> pd.DataFrame:

    # Compute all-pairs shortest paths ONCE
    cg_dist = dict(nx.all_pairs_shortest_path_length(connectivity_graph))
    tree_dist = dict(
        nx.all_pairs_shortest_path_length(tree.to_undirected(as_view=True))
    )

    rows = []

    # Only unique unordered pairs (A, B), no duplicates
    for a, b in combinations(connectivity_graph.nodes(), 2):
        rows.append(
            {
                "from": a,
                "to": b,
                "cg_path_length": cg_dist.get(a, {}).get(b, np.nan),
                "tree_path_length": tree_dist.get(a, {}).get(b, np.nan),
            }
        )

    return pd.DataFrame(rows).astype(
        {
            "cg_path_length": "float16",
            "tree_path_length": "float16",
        }
    )


def compute_hop_stretch(psp_df: pd.DataFrame) -> pd.DataFrame:
    psp_df["hop_stretch"] = psp_df["tree_path_length"] / psp_df["cg_path_length"]
    return psp_df


def hop_stretch_for_each_timestamp(repetition: "RepetitionResults") -> pd.DataFrame:
    all_hs = pd.DataFrame()

    for timestamp in sorted(repetition.neighbor_df["timestamp"].unique()):
        connectivity_graph = build_connectivity_graph(repetition, timestamp)
        tree_topology = build_tree_topology(repetition, timestamp)
        psp_df = pairwise_shortest_paths(connectivity_graph, tree_topology)
        hop_stretch_df = compute_hop_stretch(psp_df)
        hop_stretch_df["timestamp"] = timestamp

        all_hs = pd.concat([all_hs, hop_stretch_df], ignore_index=True)
    return all_hs


def get_positions_nx(repetition: "RepetitionResults") -> dict[str, tuple[float, float]]:
    return {
        row["node_id"]: (row["x"], row["y"])
        for _, row in repetition.positions_df.iterrows()
    }
