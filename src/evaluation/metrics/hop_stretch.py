import pandas as pd
import numpy as np
import networkx as nx


def build_connectivity_graph(
    neighbor_df: pd.DataFrame, timestamp: int, nodes_list: list[str] = []
) -> nx.Graph:

    G = nx.Graph()

    # Filter to specific timestamp window
    window = neighbor_df[
        (neighbor_df["timestamp"] >= timestamp - 5)
        & (neighbor_df["timestamp"] <= timestamp + 5)
    ]

    for _, row in window.iterrows():
        # Add bidirectional edge if they're neighbors
        if row["type"] in [
            "NODE_NEIGHBOR",
            "NODE_PARENT",
            "NODE_CHILD",
            "NODE_DESCENTANT",
        ]:
            G.add_edge(row["node_id"], row["neighbor"])
        else:
            raise ValueError(f"Unknown neighbor type: {row['type']}")

    for node in nodes_list:
        if node not in G:
            G.add_node(node)

    return G


def build_tree_topology(
    neighbor_df: pd.DataFrame, timestamp: int, nodes_list: list[str] = []
) -> nx.DiGraph:

    G = nx.DiGraph()

    # Filter to specific timestamp window
    window = neighbor_df[
        (neighbor_df["timestamp"] >= timestamp - 5)
        & (neighbor_df["timestamp"] <= timestamp + 5)
    ]

    for _, row in window.iterrows():
        if row["type"] == "NODE_PARENT":
            G.add_edge(row["neighbor"], row["node_id"])
        elif row["type"] == "NODE_CHILD":
            G.add_edge(row["node_id"], row["neighbor"])

    for node in nodes_list:
        if node not in G:
            G.add_node(node)

    return G


def pairwise_shortest_paths(
    connectivity_graph: nx.Graph, tree: nx.DiGraph
) -> pd.DataFrame:
    psp_df = pd.DataFrame(
        columns=["from", "to", "cg_path_length", "tree_path_length"]
    )  # Pairwise Shortest Paths

    for node_a in connectivity_graph.nodes():
        for node_b in connectivity_graph.nodes():
            if (
                node_a != node_b and node_b not in psp_df["from"].values
            ):  # Do not check both (A->B and B->A)
                try:
                    cg_length = nx.shortest_path_length(
                        connectivity_graph, source=node_a, target=node_b
                    )
                except nx.NetworkXNoPath:
                    cg_length = np.nan
                try:
                    tree_length = nx.shortest_path_length(
                        nx.Graph.to_undirected(tree, as_view=True),
                        source=node_a,
                        target=node_b,
                    )
                except nx.NetworkXNoPath:
                    tree_length = np.nan
                except nx.NodeNotFound:
                    tree_length = np.nan
                psp_df = pd.concat(
                    [
                        psp_df,
                        pd.DataFrame(
                            {
                                "from": [node_a],
                                "to": [node_b],
                                "cg_path_length": [cg_length],
                                "tree_path_length": [tree_length],
                            }
                        ),
                    ],
                    ignore_index=True,
                )
    return psp_df


def compute_hop_stretch(psp_df: pd.DataFrame) -> pd.DataFrame:
    psp_df["hop_stretch"] = psp_df["tree_path_length"] / psp_df["cg_path_length"]
    return psp_df


def hop_stretch_for_each_timestamp(
    neighbor_df: pd.DataFrame, nodes_list: list[str] = []
) -> pd.DataFrame:
    all_hs = pd.DataFrame()

    for timestamp in sorted(neighbor_df["timestamp"].unique()):
        connectivity_graph = build_connectivity_graph(
            neighbor_df, timestamp, nodes_list
        )
        tree_topology = build_tree_topology(neighbor_df, timestamp, nodes_list)
        psp_df = pairwise_shortest_paths(connectivity_graph, tree_topology)
        hop_stretch_df = compute_hop_stretch(psp_df)
        hop_stretch_df["timestamp"] = timestamp
        all_hs = pd.concat([all_hs, hop_stretch_df], ignore_index=True)
    return all_hs
