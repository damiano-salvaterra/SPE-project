from engine.Event import Event
from Layer import Layer
from rp_config import *
from typing import Optional, Any
from dataclasses import dataclass



class BeaconSendEvent(Event):
    """
    Event to send data from the application layer.
    """
    def __init__(self,  node_id: str, data: Optional[Any],
                 string_id: str, time: float, priority: int = 0, blame: Optional[Any] = None, observer: Optional[Any] = None, log_event: bool = False):
        
        super().__init__(string_id=string_id, time=time, log_event=log_event, priority=priority, blame=blame, observer=observer)
        #specific attributes for BeaconSendEevent
        self.node_id = node_id
        self.data = data


    def __str__(self):
        return f"BeaconSendEvent(node_id={self.node_id}, time={self.time}, data={str(self.data)})"



@dataclass(frozen = True)
class BeaconMessage:
    seqn: int
    metric: float
    hops: int
    parent: bytes



class NetLayer(Layer):

    def __init__(self, sink: bool):
        """
        Initialize the network layer.
        """
        super().__init__()
        
        #initialize all the timers and the parameters of the network layer
        self.metric = float('inf')
        self.seqn = 0
        self.sink = sink
        self.hops = 255
        self.parent = None

        # TODO: I need to simulate also the buffers witht he right size if i want to simulate the correct network traffic fo big networks



    def send(self):
        pass
    def recv(self):
        pass
    
    def schedule_beacon(self, time: int = TREE_BEACON_INTERVAL):
        """
        Schedule a beacon event to be sent.
        """
        data = BeaconMessage(seqn=self.seqn, metric = self.metric, hops = self.hops, parent = self.parent)
        event_string = f'{self.node.node_id}/NET/{self.node.node_id}:Beacon.{data.seqn}:BC' # Let's set this convention: NODE/BLAME/LOG ... NODE/NET/{source:data/logStuff:destination} for send events
        event = BeaconSendEvent(node_id=self.node.node_id, data = data, string_id=event_string, time = time, blame = self, observer= 
        self.node.context.scheduler.schedule(event)