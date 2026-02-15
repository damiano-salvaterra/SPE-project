from pathlib import Path

import pandas as pd

from metrics.hop_stretch import hop_stretch_for_each_timestamp


class RepetitionResults:

    _APP_LOG_FILENAME = "log_app.csv"
    _LATENCY_LOG_FILENAME = "log_e2eLat.csv"
    _PDR_LOG_FILENAME = "log_PDR.csv"
    _TARP_LOG_FILENAME = "log_tarp.csv"
    _NEIGHBOR_LOG_FILENAME = "log_NeighborTable.csv"
    _PARCHG_LOG_FILENAME = "log_ParChg.csv"
    _POSITIONS_LOG_FILENAME = "log_positions.csv"

    _PARAMETERS_FILENAME = "parameters.txt"

    def __init__(
        self,
        id: str,
        app_df: pd.DataFrame,
        latency_df: pd.DataFrame,
        pdr_df: pd.DataFrame,
        tarp_df: pd.DataFrame,
        positions_df: pd.DataFrame,
        neighbor_df: pd.DataFrame,
        parent_chg_df: pd.DataFrame,
        parameters: str,
    ):
        self.id = id
        self.app_df = app_df
        self.latency_df = (
            latency_df.drop("Unnamed: 0", axis=1, errors="ignore")
            if latency_df is not None
            else None
        )
        self.pdr_df = (
            pdr_df.drop("Unnamed: 0", axis=1, errors="ignore")
            if pdr_df is not None
            else None
        )

        if self.pdr_df is not None and self.pdr_df.source_addr.dtype == "int64":
            self.pdr_df.source_addr = self.pdr_df.source_addr.map(
                lambda x: x.to_bytes(2, "big").hex()
            )

        self.tarp_df = (
            tarp_df.astype(
                {
                    "epoch": "float16",
                    "time": "float16",
                    "hops": "float16",
                }
            )
            if tarp_df is not None
            else None
        )

        self.positions_df = positions_df
        self.parent_chg_df = (
            parent_chg_df.drop("Unnamed: 0", axis=1, errors="ignore")
            if parent_chg_df is not None
            else None
        )
        self.neighbor_df = (
            neighbor_df.astype(
                {
                    "timestamp": "float16",
                    "hops": "uint8",
                    "etx": "float16",
                    "adv_metric": "float16",
                    "age": "float16",
                    "log_num": "uint8",
                }
            ).drop(["Unnamed: 0"], axis=1, errors="ignore")
            if neighbor_df is not None
            else None
        )

        self.parameters = parameters
        self._parse_parameters()

        try:
            self._map_neighbor_addresses()
        except Exception as e:
            print(f"Error mapping neighbor addresses: {e}")
            print(
                f"Repetition ID: {self.id}, channel type: {self.channel_type}, sim_seed: {self.sim_seed}, topo_seed: {self.topo_seed}"
            )
            raise e

    def _parse_parameters(self) -> dict:
        import re

        self.is_antithetic = (
            True if re.search(r"antithetic:\s*True", self.parameters) else False
        )

        channel_type = re.search(r"channel:\s*((\w+_?)+)", self.parameters)
        self.channel_type = channel_type.group(1) if channel_type else None

        simulation_time = re.search(r"simulation_time:\s*(\d+\.\d+)", self.parameters)
        self.simulation_time = (
            float(simulation_time.group(1)) if simulation_time else None
        )

        sim_seed = re.search(r"sim_seed:\s*(\d+)", self.parameters)
        self.sim_seed = int(sim_seed.group(1)) if sim_seed else None

        topo_seed = re.search(r"topo_seed:\s*(\d+)", self.parameters)
        self.topo_seed = int(topo_seed.group(1)) if topo_seed else None

        mean_inter_arrival_time = re.search(
            r"mean_interarrival:\s*(\d+\.\d+)", self.parameters
        )
        self.mean_inter_arrival_time = (
            float(mean_inter_arrival_time.group(1)) if mean_inter_arrival_time else None
        )

        topology_type = re.search(r"topology:\s*(\w+)", self.parameters)
        self.topology_type = topology_type.group(1) if topology_type else None

    def compute_hop_stretch(self) -> pd.DataFrame:
        if self.neighbor_df is None or self.positions_df is None:
            raise ValueError(
                "Neighbor or positions data is missing, cannot compute hop stretch"
            )

        self.hop_stretch_df = hop_stretch_for_each_timestamp(self)
        return self.hop_stretch_df

    @classmethod
    def from_folder(cls, folder_path: Path) -> "RepetitionResults":
        id = folder_path.name

        latency_df = pdr_df = tarp_df = positions_df = neighbor_df = parent_chg_df = (
            None
        )

        if (folder_path / cls._APP_LOG_FILENAME).exists():
            app_df = pd.read_csv(folder_path / cls._APP_LOG_FILENAME)

        if (folder_path / cls._LATENCY_LOG_FILENAME).exists():
            latency_df = pd.read_csv(folder_path / cls._LATENCY_LOG_FILENAME)

        if (folder_path / cls._PDR_LOG_FILENAME).exists():
            pdr_df = pd.read_csv(folder_path / cls._PDR_LOG_FILENAME)

        if (folder_path / cls._TARP_LOG_FILENAME).exists():
            tarp_df = pd.read_csv(folder_path / cls._TARP_LOG_FILENAME)

        positions_df = pd.read_csv(folder_path / cls._POSITIONS_LOG_FILENAME)

        if (folder_path / cls._NEIGHBOR_LOG_FILENAME).exists():
            neighbor_df = pd.read_csv(folder_path / cls._NEIGHBOR_LOG_FILENAME)

        if (folder_path / cls._PARCHG_LOG_FILENAME).exists():
            parent_chg_df = pd.read_csv(folder_path / cls._PARCHG_LOG_FILENAME)

        with open(folder_path / cls._PARAMETERS_FILENAME, "r") as f:
            parameters = f.read()

        return cls(
            id,
            app_df,
            latency_df,
            pdr_df,
            tarp_df,
            positions_df,
            neighbor_df,
            parent_chg_df,
            parameters,
        )

    def __repr__(self):
        return f"RepetitionResults(id={self.id})"

    def _map_neighbor_addresses(self):
        if self.neighbor_df is not None:
            self.neighbor_df = self.neighbor_df.astype({"neighbor": str})
            self.neighbor_df["neighbor"] = self.neighbor_df["neighbor"].map(
                lambda x: f"Node-{int(x, 16)}"
            )

    def memory_usage(self) -> int:
        total_memory = 0
        for df in [
            self.app_df,
            self.latency_df,
            self.pdr_df,
            self.tarp_df,
            self.positions_df,
            self.neighbor_df,
            self.parent_chg_df,
            self.hop_stretch_df if hasattr(self, "hop_stretch_df") else None,
        ]:
            if df is not None:
                total_memory += df.memory_usage(index=True).sum()
        return total_memory

    def compute_interarrivals(self) -> pd.DataFrame:
        ia_df = self.app_df[self.app_df["event"].isin(["SEND", "SEND_FAIL"])]

        ia_df = ia_df.sort_values(by="time")
        ia_df["inter_arrival"] = ia_df.groupby("node_id")["time"].diff().fillna(0)

        return ia_df
