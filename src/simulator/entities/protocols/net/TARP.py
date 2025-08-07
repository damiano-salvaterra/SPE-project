from entities.protocols.common.Layer import Layer
from entities.common.Entity import Entity
from protocols.common.packets import Frame_802154, TARPPacket, TARPUnicastHeader, TARPBroadcastHeader, TARPUnicastType
from simulator.entities.physical.devices.nodes import StaticNode
from common.net_events import NetBeaconSendEvent, NetRoutingTableCleanupEvent
from enum import Enum
from dataclasses import dataclass
from typing import Dict, Any, Optional


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

class TARP(Layer, Entity):
    MAX_PATH_LENGTH = 40 # maximum number of hops before dropping the packet
    CLEANUP_INTERVAL = 15 #cleanup the routing table from expired entries every 15 seconds
    ALWAYS_INVALID_AGE = -1 # time 0. Route having this age are always invalid.
                            #In the C implementation it has value zero, but in the DES the time 0 actually exists so we need a smaller value
    TREE_BEACON_INTERVAL = 60
    RSSI_LOW_THR = -85
    RSSI_HIGH_REF = -35
    DELTA_ETX_MIN = 0.3
    THR_H = 100

    #NullRDC mode constants
    ALPHA = 0.9


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


    def __init__(self, host: StaticNode, sink: bool = False):
        Layer.__init__(self, host = host)
        Entity.__init__(self)
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


    def _reset_connection_status(self, seqn: int):
        '''resets the protocol status when a beacon with higher seqnum is received'''
        for entry in self.nbr_tbl.values(): 
            if entry.type == NodeType.NODE_DESCENTANT: #make descendants old enough to be removed (sounds very bad, but is necessary)
                entry.age = TARP.ALWAYS_INVALID_AGE
            elif entry.type == NodeType.NODE_CHILD or entry.type == NodeType.NODE_PARENT: #downgrade all the other entries to neighbors
                entry.type = NodeType.NODE_NEIGHBOR

        self.parent = None
        self.metric = 0 if self.sink else float('inf')
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


    def _forward_data(self, header: TARPUnicastHeader, payload: Any):
        '''called when unicast packets has to be forwarded'''
        
        nexthop = self._nbr_tbl_lookup(header.d_addr)
        net_packet = TARPPacket(header = header, APDU = payload)
        self.host.mac.send(payload = net_packet, nexthop = nexthop)            


    def _beacon_timer_cb(self):
        '''callback for the beacon timer expiration'''

        if self.sink:
            new_seqn = self.seqn + 1
            self._reset_connection_status(new_seqn)
            send_beacon_time = self.host.context.scheduler.now() + TARP.TREE_BEACON_INTERVAL
            send_beacon_event = NetBeaconSendEvent(time=send_beacon_time, blame=self, callback=self._beacon_timer_cb)
            self.host.context.scheduler.schedule(send_beacon_event) # schedule next beacon flood

        broadcast_header = TARPBroadcastHeader(seqn=self.seqn, metric_q124=self.metric, hops=self.hops, parent=self.parent)
        self._broadcast_send(broadcast_header, data = None)
        



    def _bc_recv(self, payload: TARPPacket, tx_addr: bytes):
        '''
        function called from receive() function when it understands tha t is receiving a broadcast
        '''
        rssi = self.host.mac.get_last_packet_rssi()
        if rssi < TARP.RSSI_LOW_THR:
            return #discard beacon if too low rssi
        
        header: TARPBroadcastHeader = payload.header
        
        tx_entry = self.nbr_tbl.get(tx_addr)

        if tx_entry: # if entry already exists, refresh it and update the metric
            self._nbr_tbl_refresh(addr=tx_addr)
            tx_entry.adv_metric = header.metric_q124
        else: #add a new neighbor
            tx_entry = self.TARPRoute()



    def receive(self, payload: TARPPacket, tx_addr: bytes):
        #first, understand if it is a broadcast or unicast, and then delegate to specific functions
        # in Contiki the incoming packet is dispatched to the correct function by lower layers
        if isinstance(payload.header, TARPUnicastHeader):
            self._uc_recv(payload)
        elif isinstance(payload.header, TARPBroadcastHeader):
            self._bc_recv(payload, tx_addr)
    ##################################################################################
    '''utils functions implemented in files different from rp.c'''
    
    def _broadcast_send(self, header: TARPBroadcastHeader, data: Optional[Any] = None):
        broadcast_packet = TARPPacket(header=header, APDU=data)
        b_addr = Frame_802154.broadcast_linkaddr
        self.host.mac.send(payload = broadcast_packet, nexthop=b_addr)

        
    def _nbr_tbl_lookup(self, dst_addr: bytes) -> bytes: #lookup the table, returns the nexthop if any, otherwise default route to parent
        nexthop = self.parent
        if dst_addr in self.nbr_tbl.keys():
            nexthop = self.nbr_tbl[dst_addr].nexthop
        return nexthop
    

    def _nbr_tbl_refresh(self, addr: bytes):
        if addr in self.nbr_tbl.keys():
            self.nbr_tbl[addr].age = self.host.context.scheduler.now()

    def _nbr_tbl_cleanup_cb():
        pass