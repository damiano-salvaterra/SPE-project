from entities.protocols.common.Layer import Layer
from entities.common.Entity import Entity
from protocols.common.packets import Frame_802154, TARPPacket, TARPUnicastHeader, TARPBroadcastHeader, TARPUnicastType
from simulator.entities.physical.devices.nodes import StaticNode
from common.net_events import NetBeaconSendEvent, NetRoutingTableCleanupEvent,NetTopologyReportSendEvent
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

    #NullRDC mode constants  and delays
    ALPHA = 0.9
    TREE_BEACON_FORWARD_DELAY = 1 / 10

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

        rng_id = f"NODE:{self.host.id}/NET_TARP"
        self.host.context.random_manager.create_stream(rng_id)
        self.rng = self.host.context.random_manager.get_stream(rng_id)
        
        self._bootstrap_TARP() # bootstrap the protocol



    def _bootstrap_TARP(self):
        if self.sink: # if the sink, init your status and schedule the first beaocn
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
        

    def _subtree_report_cb(self):
        pass

    def _bc_recv(self, payload: TARPPacket, tx_addr: bytes):
        '''
        function called from receive() function when it understands tha t is receiving a broadcast
        '''
        rssi = self.host.mac.get_last_packet_rssi()
        if rssi < TARP.RSSI_LOW_THR:
            return #discard beacon if too low rssi
        
        header: TARPBroadcastHeader = payload.header
        current_time = self.host.context.scheduler.now()

        
        tx_entry = self.nbr_tbl.get(tx_addr)

        if tx_entry: # if entry already exists, refresh it and update the metric
            self._nbr_tbl_refresh(addr=tx_addr)
            tx_entry.adv_metric = header.metric_q124
        else: #add a new neighbor
            tx_entry = self.TARPRoute(
                type=NodeType.NODE_NEIGHBOR,
                age = current_time,
                nexthop=tx_addr,
                hops=header.hops,
                etx = self._etx_est_rssi(rssi),
                num_tx = 0,
                num_ack=0,
                adv_metric=header.metric_q124
            )
            self.nbr_tbl[tx_addr] = tx_entry
        
        #manage epoch change
        if not self.sink and header.seqn > self.seqn:
            self._reset_connection_status(header.seqn)

        #parent selection logic
        new_metric = self._metric(header.metric_q124, tx_entry.etx)

        if self.preferred(new_metric, self.metric): # if metric from this transmitter is better, st it as a parent
            self.parent = tx_addr
            self.metric = new_metric
            self.hops = header.hops + 1

            #promote entry to parent
            tx_entry.type = NodeType.NODE_PARENT

            #schedule beacon forward
            beacon_forward_jitter = self.rng.uniform(low=0, high= 0.125) #random jitter for beacon forward
            beacon_forward_time  = current_time + TARP.TREE_BEACON_FORWARD_DELAY + beacon_forward_jitter
            beacon_forward_event = NetBeaconSendEvent(time=beacon_forward_time, blame=self, callback=self._beacon_timer_cb)
            self.host.context.scheduler.schedule(beacon_forward_event)

            #schedule first topology report
            first_report_time = current_time + self._subtree_report_base_delay()
            first_report_event = NetTopologyReportSendEvent(time = first_report_time, blame=self, callback=self._subtree_report_cb)
            self.host.context.scheduler.schedule(first_report_event)

        else: 
            '''
            Either the transmitter is a neighbor with a worse metric, or it is a child that is forwarding its beacon.
            If it is a child, then it has to be added to the buffer if it is still advertising this node as
            a parent, otherwise it has to be removed from the buffer, because it found a better parent.
            '''
            



        

        




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


    def _etx_est_rssi(rssi: float) -> float:
        '''heuristic for the etx based on rssi'''
        if rssi > TARP.RSSI_HIGH_REF:
            return 1.0
        if rssi < TARP.RSSI_LOW_THR:
            return 10.0
        span = TARP.RSSI_HIGH_REF - TARP.RSSI_LOW_THR
        offset = TARP.RSSI_HIGH_REF - rssi
        frac = offset / span

        return 1.0 + frac * 9.0
    
    def _metric(self, adv_metric: float, etx: float) -> float:
        return adv_metric + etx
    
    def _metric_improv_thr(self, cur_metric: float):
        if cur_metric <= 0.0:
            return float('inf')
        thr = TARP.THR_H / cur_metric
        return TARP.DELTA_ETX_MIN if thr < TARP.DELTA_ETX_MIN else thr
    
    def _preferred(self, new_m: float, cur_m: float) -> bool:
        thr = self._metric_improv_thr(cur_m)
        return (new_m + thr) < cur_m

    def _subtree_report_base_delay(self) -> float:
        return (5 / self.hops) + (self.rng(low=0, hig=0.4))