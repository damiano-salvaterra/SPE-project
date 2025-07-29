from environment.geometry import CartesianCoordinate
from network.phy.PhyLayer import PhyLayer
from network.mac.MAC802_15_4Layer import MAC802_15_4
from network.net.NetTARPLayer import TARP
from applications.Application import Application
from applications.random_traffic import RandomTrafficApplication
from engine.common.SimulationContext import SimulationContext

'''
This class is an orchestrator for the stack layers.
all the events from the various layers are sent to the Node object that dipatches them to the correct entities
'''
class Node():
    def __init__(self, node_id: str, position: CartesianCoordinate, application: Application, context: SimulationContext):
        self.id = node_id
        self.position = position
        self.context = context
        self.phy = PhyLayer(self)
        self.mac = MAC802_15_4(self)
        self.net = TARP(self)
        self.app = application


    


