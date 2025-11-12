from pathlib import Path
import json

import pandas as pd


class RepetitionResults:
    def __init__(
        self,
        id: str,
        app_df: pd.DataFrame,
        latency_df: pd.DataFrame,
        pdr_df: pd.DataFrame,
        tarp_df: pd.DataFrame,
        parameters: dict,
    ):
        self.id = id
        self.app_df = app_df
        self.latency_df = latency_df
        self.pdr_df = pdr_df
        self.tarp_df = tarp_df
        self.parameters = parameters

    @classmethod
    def from_folder(cls, folder_path: Path) -> "RepetitionResults":
        id = folder_path.name
        app_df = pd.read_csv(folder_path / "log_app.csv")
        latency_df = pd.read_csv(folder_path / "log_e2eLat.csv")
        pdr_df = pd.read_csv(folder_path / "log_PDR.csv")
        tarp_df = pd.read_csv(folder_path / "log_tarp.csv")

        with open(folder_path / "parameters.json", "r") as f:
            parameters = json.load(f)

        return cls(id, app_df, latency_df, pdr_df, tarp_df, parameters)

    def __repr__(self):
        return f"RepetitionResults(id={self.id})"
