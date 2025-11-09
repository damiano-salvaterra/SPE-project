from simulator.environment.geometry import CartesianCoordinate
from simulator.entities.protocols.phy.SimplePhyLayer import SimplePhyLayer
from simulator.entities.protocols.radio_dc.NullRDC import NullRDC
from simulator.entities.protocols.mac.ContikiOS_MAC_802154 import (
    ContikiOS_MAC_802154_Unslotted,
)
from simulator.entities.protocols.net.tarp import TARPProtocol
from simulator.entities.common import NetworkNode
from simulator.entities.applications.Application import Application
from simulator.engine.common.SimulationContext import SimulationContext


# TODO: to remove circular dependencies we should define a Node interface and use it for the imports
class StaticNode(NetworkNode):
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
        super().__init__()
        self._id = node_id
        self._linkaddr = linkaddr
        self.position = position
        self._context = context
        self._phy = SimplePhyLayer(self)
        self._rdc = NullRDC(self)
        self._mac = ContikiOS_MAC_802154_Unslotted(self)
        self._net = TARPProtocol(self, sink=is_sink)
        self._app = application

    @property
    def id(self) -> str:
        return self._id

    @property
    def linkaddr(self) -> bytes:
        return self._linkaddr

    @property
    def context(self) -> SimulationContext:
        return self._context

    @property
    def phy(self) -> SimplePhyLayer:
        return self._phy

    @property
    def rdc(self) -> NullRDC:
        return self._rdc

    @property
    def mac(self) -> ContikiOS_MAC_802154_Unslotted:
        return self._mac

    @property
    def net(self) -> TARPProtocol:
        return self._net

    @property
    def app(self) -> Application:
        return self._app