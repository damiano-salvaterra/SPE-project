#from simulator.entities.physical.devices.nodes import StaticNode
from simulator.entities.protocols.phy.common.Transmission import Transmission
from typing import List, Dict, TYPE_CHECKING
import copy

if TYPE_CHECKING:
    from simulator.entities.physical.devices.nodes import StaticNode

'''This class implements the observer of the wireless channel
when a node starts receiving a packet. This object has no particular domain meaning (for now):
it is only a utiliy object to observing the evolving state in the wireless channel during the reception
'''
class ReceptionSession:
    '''
    Support class that holds the concurrent transmissions
    and relative timings
    '''
    class ReceptionSegment:

        def __init__(self, interferers: Dict["StaticNode", "Transmission"], t0: float, t1: float = None):
            self.t0 = t0
            self.t1 = t1
            self.interferers: Dict["StaticNode", "Transmission"] = interferers # keep a dict to remove elements fast
                                                                    # end get the Node object fast later for the SINR

    
    def __init__(self, receiving_node: "StaticNode", capturing_tx: "Transmission", start_time: float, end_time: float = None):
        self.receiving_node = receiving_node
        self.capturing_tx = capturing_tx
        self.start_time = start_time
        self.end_time = end_time
        self.reception_segments: List[ReceptionSession.ReceptionSegment] = [] # keep track of all the segments with all the interferers.
                                                                          # the point of this is to register all the amount of interference during the reception session
                                                                          # so at the end of the reception we can process this and decide if the collision occured or not
                                                                          # (example (this project policy): find the segments with the highest amount of SINR and decide based on that) 

    def notify_tx_start(self, transmission: "Transmission"):
        '''
        create a new segment with the current interferes plus the new one
        '''
        interferers_snapshot = copy.deepcopy(self.reception_segments[-1].interferers)
        interferers_snapshot[transmission.transmitter] = transmission
        new_segment = ReceptionSession.ReceptionSegment(t0 = self.receiving_node.context.scheduler.now(), interferers = interferers_snapshot)
        self.reception_segments.append(new_segment)



    def notify_tx_end(self, transmission: "Transmission"):
        '''
        create a new segment with the old interferes minus the ended one.
        Set also t1 for the just finished segment
        '''
        self.reception_segments[-1].t1 = self.receiving_node.context.scheduler.now()
        interferers_snapshot = copy.deepcopy(self.reception_segments[-1].interferers)
        interferers_snapshot.pop(transmission.transmitter) # remove the ended transmission
        new_segment = ReceptionSession.ReceptionSegment(t0=self.receiving_node.context.scheduler.now(), interferers = interferers_snapshot)
        self.reception_segments.append(new_segment)