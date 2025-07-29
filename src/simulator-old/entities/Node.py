from engine.NodeContext import NodeContext
from layers.Layer import Layer
from layers.PhyLayer import PhyLayer
from layers.MacLayer import MacLayer
from layers.NetLayer import NetLayer
from layers.AppLayer import AppLayer

class Node:
    def __init__(self, node_id: str, sink: bool, linkaddr: bytes, context: NodeContext):
        self.node_id = node_id
        self.context = context

        # instantiate layers
        self._phy_layer: Layer = PhyLayer(self)
        self._mac_layer: Layer = MacLayer(self)
        self._net_layer: Layer = NetLayer(self, sink, linkaddr)
        self._app_layer: Layer = AppLayer(self)

