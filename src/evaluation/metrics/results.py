from pathlib import Path

from .repetition import RepetitionResults


class SimulationResults:
    def __init__(self, id: str, repetitions: list[RepetitionResults]):
        self.id = id
        self.repetitions = repetitions

    @classmethod
    def from_folder(cls, folder_path: Path) -> "SimulationResults":
        repetitions = []

        print(f"Loading simulation results from folder: {folder_path}")
        for rep_folder in folder_path.iterdir():
            if rep_folder.is_dir():
                repetition = RepetitionResults.from_folder(rep_folder)
                repetitions.append(repetition)

        return cls(id=folder_path.name, repetitions=repetitions)

    def __repr__(self) -> str:
        return f"SimulationResults(id={self.id}, repetitions={self.repetitions})"
