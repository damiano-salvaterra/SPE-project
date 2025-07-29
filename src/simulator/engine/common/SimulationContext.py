from engine.RandomManager import RandomManager
from engine.Scheduler import Scheduler

'''
This class provides the context of the simulation to the entities
'''

class SimulationContext:
    def __init__(self, scheduler: Scheduler, random_manager: RandomManager):
        self.scheduler = scheduler
        self.random_manager = random_manager
