from pathlib import Path

from .repetition import RepetitionResults


class ChannelResults:
    channel_type: str
    repetitions: list[RepetitionResults]

    def __init__(self, channel_type: str, repetitions: list[RepetitionResults]):
        self.channel_type = channel_type
        self.repetitions = repetitions

    @classmethod
    def from_folder(cls, folder_path: Path) -> "ChannelResults":
        channel_type = folder_path.name
        repetitions = []
        for repetition_folder in folder_path.iterdir():
            if repetition_folder.is_dir():
                repetitions.append(RepetitionResults.from_folder(repetition_folder))

        return cls(channel_type, repetitions)

    def __repr__(self):
        return f"ChannelResults(channel_type={self.channel_type}, repetitions={len(self.repetitions)})"
