#from simulator.entities.physical.devices.nodes import StaticNode
from simulator.entities.protocols.phy.common.Transmission import Transmission
from typing import List, Dict, TYPE_CHECKING
import copy

if TYPE_CHECKING:
    from simulator.entities.physical.devices.nodes import StaticNode

'''This class implements the observer for the incoming transmissions
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
            self.interferers: List["Transmission"] = interferers #list of interferers

    
    def __init__(self, receiving_node: "StaticNode", capturing_tx: "Transmission", interferers: List["Transmission"], start_time: float, end_time: float = None):
        self.receiving_node = receiving_node
        self.capturing_tx = capturing_tx
        self.start_time = start_time
        self.end_time = end_time
        self.reception_segments: List[ReceptionSession.ReceptionSegment] = [] # keep track of all the segments with all the interferers.
                                                                          # the point of this is to register all the amount of interference during the reception session
                                                                          # so at the end of the reception we can process this and decide if the collision occured or not
                                                                          # (example (this project policy): find the segments with the highest amount of SINR and decide based on that) 
        initial_segment = self.ReceptionSegment(t0=self.start_time, interferers=copy.copy(interferers))
        self.reception_segments.append(initial_segment)

    def notify_tx_start(self, transmission: "Transmission"):
        '''
        create a new segment with the current interferes plus the new one
        '''
        interferers_snapshot = copy.copy(self.reception_segments[-1].interferers)
        interferers_snapshot.append(transmission)
        new_segment = ReceptionSession.ReceptionSegment(t0 = self.receiving_node.context.scheduler.now(), interferers = interferers_snapshot)
        self.reception_segments.append(new_segment)



    def notify_tx_end(self, transmission: "Transmission"):
        '''
        create a new segment with the old interferes minus the ended one.
        Set also t1 for the just finished segment
        If the ended transmission is the one that is being captured, do nothing
        '''

    
        #print("--- DEBUG: ReceptionSession.notify_tx_end ---")
        #print(f"Current Simulation Time: {self.receiving_node.context.scheduler.now():.6f}s")
        #print(f"This Node: {self.receiving_node.id}")
        #print(f"Attempting to remove transmitter: {transmission.transmitter.id}")
        #print(f"Interferers in the current segment: {[tx.transmitter.id for tx in self.reception_segments[-1].interferers]}")
        #print("---------------------------------------------")

        if self.capturing_tx == transmission:
            #print("  - Action: This was the captured TX. No change to interferers list.")
            #print("---------------------------------------------")
            return

        self.reception_segments[-1].t1 = self.receiving_node.context.scheduler.now()
        interferers_snapshot = copy.copy(self.reception_segments[-1].interferers)

        if transmission in interferers_snapshot:
            interferers_snapshot.remove(transmission) # remove the ended transmission
            #print("  - Action: Removed from interferers list.")
        else:
            #print("  - WARNING: Ended TX was not in the interferers list as expected.")
            pass
        new_segment = ReceptionSession.ReceptionSegment(t0=self.receiving_node.context.scheduler.now(), interferers = interferers_snapshot)
        self.reception_segments.append(new_segment)
        #print("---------------------------------------------")

        
        #if self.capturing_tx != transmission:
        #    self.reception_segments[-1].t1 = self.receiving_node.context.scheduler.now()
        #    interferers_snapshot = copy.copy(self.reception_segments[-1].interferers)
#
        #    interferers_snapshot.remove(transmission) # remove the ended transmission
#
        #    
        #    new_segment = ReceptionSession.ReceptionSegment(t0=self.receiving_node.context.scheduler.now(), interferers = interferers_snapshot)
        #    self.reception_segments.append(new_segment)