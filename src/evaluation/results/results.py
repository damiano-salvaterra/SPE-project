from pathlib import Path
from typing import Generator

from .topology_results import TopologyResults
from .repetition import RepetitionResults


class Results:
    id: str
    topologies: list[TopologyResults]

    def __init__(self, id: str, topologies: list[TopologyResults]):
        self.id = id
        self.topologies = topologies

    @classmethod
    def from_folder(
        cls, folder_path: Path, verbose: bool = True, whitelist: list[str] | None = None
    ) -> "Results":
        id = folder_path.name
        topologies = []
        for topology_folder in folder_path.iterdir():
            if whitelist is not None and topology_folder.name not in whitelist:
                if verbose:
                    print(
                        f"Skipping topology {topology_folder.name} as it's not in the whitelist"
                    )
                continue
            if topology_folder.is_dir():
                if verbose:
                    print(
                        f"Reading topology results from folder: {topology_folder.name}"
                    )
                topologies.append(TopologyResults.from_folder(topology_folder))

        return cls(id, topologies)

    def for_each_repetition(self) -> Generator[RepetitionResults, None, None]:
        for topology in self.topologies:
            for channel in topology.channels:
                for repetition in channel.repetitions:
                    yield repetition

    def __repr__(self):
        return f"Results(id={self.id}, topologies={len(self.topologies)})"
