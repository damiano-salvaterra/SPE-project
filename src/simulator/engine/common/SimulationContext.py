from simulator.engine.random import RandomManager
from simulator.engine.Scheduler import Scheduler


class SimulationContext:
    """
    This class provides the context of the simulation to the entities
    """

    def __init__(self, scheduler: Scheduler, random_manager: RandomManager):
        self.scheduler = scheduler
        self.random_manager = random_manager
