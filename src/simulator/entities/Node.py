from engine.NodeContext import NodeContext
from layers.Layer import Layer
from layers.PhyLayer import PhyLayer
from layers.MacLayer import MacLayer
from layers.NetLayer import NetLayer
from layers.AppLayer import AppLayer

class Node:
    def __init__(self, node_id: str, sink: bool, linkaddr: bytes, context: NodeContext):
        self.node_id = node_id
        self.sink = sink
        self.linkaddr = linkaddr
        self.context = context

        # instantiate layers
        self.phy_layer: Layer = PhyLayer(self.context.topology)
        self.mac_layer: Layer = MacLayer(self.context)
        self.net_layer: Layer = NetLayer(self.context)


        traffic_generator = self.context.random_manager.create_stream(f"{self.node_id}_app_traffic")
        node_ids = self.context.topology.get_node_ids()
        self.app_layer: Layer = AppLayer(self.node_id, node_ids, self.net_layer, traffic_generator, self.context.scheduler)

