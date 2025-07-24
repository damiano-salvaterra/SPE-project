from Layer import Layer
from NetLayer import NetLayer
from engine.Scheduler import Scheduler
from engine.Event import Event
import numpy as np
from typing import List, Optional


class AppSendEvent(Event):
    """
    Event to send data from the application layer.
    """
    def __init__(self,  node_id: str, destination: str,
                 unique_id: int, time: float, blame: Optional[str] = None):
        
        super().__init__(unique_id=0, string_id="AppSendEvent", time=time, log_event=False)
        #specific attributes for AppSendEvent
        self.node_id = node_id
        self.destination = destination

    def __str__(self):
        return f"AppSendEvent(node_id={self.node_id}, destination={self.destination}, time={self.time}, blame={self.blame})"


'''
This class implements an application layer for the simulator.
The only point of the application is to generate random traffic to random nodes
and to receive traffic from the network layer.
'''
class AppLayer(Layer):

    def __init__(self, node_id: str, node_ids: List[str], network_layer: NetLayer, traffic_generator: np.random.Generator):
        """
        Initialize the application layer.
        """
        self.node_id = node_id
        self.node_ids = node_ids # app layer do not necessarily know the real addresses
        self.network_layer = network_layer
        self.traffic_generator = traffic_generator


    def send(self): # TODO: used by the scheduler when the event is triggered. The Core is the on who schedule the event
        """
        Generate random traffic and send it to a random node via the network layer.
        """
        #TODO: log this
        random_destination = self.traffic_generator.choice(self.node_ids)
        data = f"Data from {self.node_id} to {random_destination}"
        self.network_layer.send(self.node_id, random_destination, data)


    def recv(self, source, data):
        """
        Receive data from the network layer.
        """
        # TODO: log this
        pass