from environment.geometry import CartesianCoordinate
from protocols.phy.SimplePhyLayer import SimplePhyLayer
from protocols.radio_dc.NullRDC import NullRDC
from protocols.mac.ContikiOS_MAC_802154 import ContikiOS_MAC_802154_Unslotted
from simulator.entities.protocols.net.TARP import TARP
from applications.Application import Application
from engine.common.SimulationContext import SimulationContext

'''
This class is an orchestrator for the stack layers.
all the events from the various layers are sent to the Node object that dipatches them to the correct entities
'''
class Node():
    def __init__(self, node_id: str, linkaddr: bytes, position: CartesianCoordinate, application: Application, context: SimulationContext):
        self.id = node_id
        self.linkaddr = linkaddr
        self.position = position
        self.context = context
        self.phy = SimplePhyLayer(self)
        self.rdc = NullRDC(self)
        self.mac = ContikiOS_MAC_802154_Unslotted(self)
        self.net = TARP(self)
        self.app = application


    


