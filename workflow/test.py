from typing import NamedTuple

ExpResult = float

class Experiment(NamedTuple):
    well: str
    acid_volume: float
    base_volume: float

def execute_experiment(batch: list[Experiment]) -> list[ExpResult]:
    pass