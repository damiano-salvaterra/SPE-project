from Layer import Layer
from NetLayer import NetLayer
from Node import Node
from engine.Event import Event
import numpy as np
from typing import List, Optional, Any


class AppSendEvent(Event):
    """
    Event to send data from the application layer.
    """
    def __init__(self,  node_id: str, destination: str, data: Optional[Any],
                string_id: str, time: float, priority: int = 0, blame: Optional[Any] = None, observer: Optional[Any] = None, log_event: bool = False):
        
        super().__init__(string_id=string_id, time=time, log_event=log_event, priority=priority, blame=blame, observer=observer)
        #specific attributes for AppSendEvent
        self.node_id = node_id
        self.destination = destination
        self.data = data

    def __str__(self):
        return f"AppSendEvent(node_id={self.node_id}, destination={self.destination}, time={self.time}, data={str(self.data)})"


'''
This class implements an application layer for the simulator.
The only point of the application is to generate random traffic to random nodes
and to receive traffic from the network layer.
'''
class AppLayer(Layer):

    def __init__(self, node: Node):
        """
        Initialize the application layer.
        """
        super.__init__(node)
        
        #counters
        self.app_packets_sent_to_net_layer = 0
        self.app_packets_received_from_net_layer = 0


    def send(self, event: AppSendEvent): # TODO: used by the scheduler when the event is triggered. The Core is the on who schedule the event
        """
        Generate random traffic and send it to a random node via the network layer.
        """
        #TODO: log this
        self.network_layer.send(self.node_id,event.destination, event.data)
        self.app_packets_sent_to_net_layer += 1


    def recv(self, source, data):
        """
        Receive data from the network layer.
        """
        # TODO: log this
        self.app_packets_received_from_net_layer += 1