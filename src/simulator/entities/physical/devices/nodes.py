from simulator.environment.geometry import CartesianCoordinate
from simulator.entities.protocols.phy.SimplePhyLayer import SimplePhyLayer
from simulator.entities.protocols.radio_dc.NullRDC import NullRDC
from simulator.entities.protocols.mac.ContikiOS_MAC_802154 import (
    ContikiOS_MAC_802154_Unslotted,
)
from simulator.entities.protocols.net.tarp.TARP import TARP
from simulator.entities.common.Entity import Entity
from simulator.applications.Application import Application
from simulator.engine.common.SimulationContext import SimulationContext


# TODO: to remove circular dependencies we should define a Node interface and use it for the imports
class StaticNode(Entity):
    """
    This class is an orchestrator for the stack layers.
    all the events from the various layers are sent to the Node object that dipatches them to the correct entities
    """

    def __init__(
        self,
        node_id: str,
        linkaddr: bytes,
        position: CartesianCoordinate,
        application: Application,
        context: SimulationContext,
        is_sink=False,
    ):
        Entity.__init__(self)
        self.id = node_id
        self.linkaddr = linkaddr
        self.position = position
        self.context = context
        self.phy = SimplePhyLayer(self)
        self.rdc = NullRDC(self)
        self.mac = ContikiOS_MAC_802154_Unslotted(self)
        self.net = TARP(self, sink=is_sink)
        self.app = application
