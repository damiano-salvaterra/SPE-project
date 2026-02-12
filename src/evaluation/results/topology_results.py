from pathlib import Path
from typing import Generator


from .channel_results import ChannelResults
from .repetition import RepetitionResults


class TopologyResults:
    topology_type: str
    channels: list[ChannelResults]

    def __init__(self, topology_type: str, channels: list[ChannelResults]):
        self.topology_type = topology_type
        self.channels = channels

    @classmethod
    def from_folder(cls, folder_path: Path) -> "TopologyResults":
        topology_type = folder_path.name
        channels = []
        for channel_folder in folder_path.iterdir():
            if channel_folder.is_dir():
                channels.append(ChannelResults.from_folder(channel_folder))

        return cls(topology_type, channels)

    def for_each_repetition(self) -> Generator[RepetitionResults, None, None]:
        for channel in self.channels:
            for repetition in channel.repetitions:
                yield repetition

    def __repr__(self):
        return f"TopologyResults(topology_type={self.topology_type}, channels={len(self.channels)})"
