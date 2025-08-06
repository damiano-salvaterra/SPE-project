from entities.protocols.common.Layer import Layer
from protocols.common.packets import AppRequest, TARPPacket, TARPUnicastHeader, TARPBroadcastHeader, TARPUnicastType
from entities.physical.devices.Node import Node
from common.net_events import NetBeaconSendEvent, NetRoutingTableCleanupEvent
from enum import Enum
from dataclasses import dataclass
from typing import Dict, Any


'''
This class implements TARP (Tree-based Any-to-any Routing Protocol).
It follows exactly the implementation of the C source code (readapted in pythonic
way and avoiding some C specific coding paradigm, obviously).
'''

class NodeType(Enum):
    NODE_PARENT = 0
    NODE_CHILD = 1
    NODE_DESCENTANT = 2
    NODE_NEIGHBOR = 3

class TARP(Layer):
    MAX_PATH_LENGTH = 40 # maximum number of hops before dropping the packet
    CLEANUP_INTERVAL = 15 #cleanup the routing table from expired entries every 15 seconds
    ALWAYS_INVALID_AGE = -1 # time 0. Route having this age are always invalid.
                            #In the C implementation it has value zero, but in the DES the time 0 actually exists so we need a smaller value

    @dataclass
    class TARPRoute: #routing table entry class
        type: NodeType
        age: float
        nexthop: bytes
        hops: int
        etx: float
        num_tx: int
        num_ack: int
        adv_metric: float

    class RouteStatus(Enum):
        STATUS_ADD = 1
        STATUS_REMOVE = 0


    def __init__(self, host: Node, sink: bool = False):
        super().__init__(self)
        self.host = host
        self.sink = sink
        self.nbr_tbl: Dict[bytes, TARP.TARPRoute] = {} # routing table. key: linkaddr, value: TarpRoute record

        #TARP state
        self.metric = float('inf')
        self.seqn = 0
        self.hops = TARP.MAX_PATH_LENGTH + 1
        self.tpl_buf: Dict[bytes, TARP.RouteStatus] = {} #topology diff buffer

        if sink: # if the sink, init your status and schedule the first beaocn
            self.metric = 0
            self.hops = 0
            send_beacon_time = self.host.context.scheduler.now() + 1 # send a beaacon after one second 
            send_beacon_event = NetBeaconSendEvent(time=send_beacon_time, blame=self, callback=self._beacon_timer_cb)
            self.host.context.scheduler.schedule(send_beacon_event)

        cleanup_time = self.host.context.scheduler.now() + TARP.CLEANUP_INTERVAL
        cleanup_event = NetRoutingTableCleanupEvent(time = cleanup_time, blame = self, callback=self._nbr_tbl_cleanup_cb)
        self.host.context.scheduler.schedule(cleanup_event) #schedule first cleanup

    def _flush_tpl_buf(self): #flushes the diff buffer
        self.tpl_buf.clear()


    def _reset_connection_status(self, seqn: int, sink: bool):
        '''resets the protocol status when a beacon with higher seqnum is received'''
        for entry in self.nbr_tbl.values(): 
            if entry.type == NodeType.NODE_DESCENTANT: #make descendants old enough to be removed (sounds very bad, but is necessary)
                entry.age = TARP.ALWAYS_INVALID_AGE
            elif entry.type == NodeType.NODE_CHILD or entry.type == NodeType.NODE_PARENT: #downgrade all the other entries to neighbors
                entry.type = NodeType.NODE_NEIGHBOR

        self.parent = None
        self.metric = 0 if sink else float('inf')
        self.seqn = seqn
        self._flush_tpl_buf() # flush the diff buffer, no longer necessary
        self._nbr_tbl_cleanup_cb() #cleanup table

    
    def send(self, payload: Any, destination: bytes) -> bool:
        '''
        Returns true if sent succesfully.
        Called only by the application directly, forwarding logic is somewhere else
        '''
        if not self.sink and self.parent == None:
            return False # TODO: this may be useful to put in an instance status attribute, to be monitored from the outside
        
        nexthop = self._nbr_tbl_lookup(destination)
        packet_header = TARPUnicastHeader(type = TARPUnicastType.UC_TYPE_DATA, s_addr = self.host.linkaddr, d_addr = destination, hops = 0)
        net_packet = TARPPacket(header = packet_header, APDU = payload)
        self.host.mac.send(payload = net_packet, nexthop = nexthop)            

        
    
    
    def _nbr_tbl_lookup(self, dst_addr: bytes) -> bytes: #lookup the table, returns the nexthop if any, otherwise default route to parent
        nexthop = self.parent
        if dst_addr in self.nbr_tbl.keys():
            nexthop = self.nbr_tbl[dst_addr].nexthop
        return nexthop
    

    def _beacon_timer_cb():
        pass

    def _nbr_tbl_cleanup_cb():
        pass