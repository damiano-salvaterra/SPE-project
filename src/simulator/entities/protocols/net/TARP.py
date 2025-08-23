from simulator.entities.protocols.common.Layer import Layer
from simulator.entities.common.Entity import Entity
from simulator.entities.protocols.common.packets import Frame_802154, TARPPacket, TARPUnicastHeader, TARPBroadcastHeader, TARPUnicastType
#from simulator.entities.physical.devices.nodes import StaticNode
from simulator.entities.protocols.net.common.net_events import NetBeaconSendEvent, NetRoutingTableCleanupEvent,NetTopologyReportSendEvent
from enum import Enum
from dataclasses import dataclass
from typing import Dict, Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from simulator.entities.physical.devices.nodes import StaticNode

'''
This class implements TARP (Tree-based Any-to-any Routing Protocol).
It follows exactly the implementation of the C source code (readapted in pythonic
way and avoiding some C specific coding paradigm, obviously).
source:  https://github.com/DaMole98/LPWN-project2/tree/main
'''

class NodeType(Enum):
    NODE_PARENT = 0
    NODE_CHILD = 1
    NODE_DESCENTANT = 2
    NODE_NEIGHBOR = 3



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


def _valid(current_time: float, route: "TARP.TARPRoute") ->bool:
    return current_time - route.age < TARP.ENTRY_EXPIRATION_TIME


def _metric(adv_metric: float, etx: float) -> float:
    return adv_metric + etx


def _metric_improv_thr(cur_metric: float):
    if cur_metric <= 0.0:
        return float('inf')
    thr = TARP.THR_H / cur_metric
    return TARP.DELTA_ETX_MIN if thr < TARP.DELTA_ETX_MIN else thr


def _preferred(new_m: float, cur_m: float) -> bool:
    thr = _metric_improv_thr(cur_m)
    return (new_m + thr) < cur_m

def _etx_update(num_tx: int, num_ack: int, o_etx: float, rssi: float):
    n_etx = 0.0
    if num_ack == 0 or TARP.ALPHA == 1:
        n_etx = _etx_est_rssi(rssi)
    else:
        #EWMA filtering
        n_etx = num_tx / num_ack
        n_etx = TARP.ALPHA * o_etx + (1 - TARP.ALPHA) * n_etx
    return n_etx

class TARP(Layer, Entity):
    MAX_STAT_PER_FRAGMENT = 37 #Max bytes allowed per packet (PHY) in 802.15.4 is 127. 
                            # Approximately, taking out all the overhead due to header (TARP included), we are left with around 112 bytes
                            # now, each status voice in the report is 3 bytes, plus une byte for the number of voices. so we can send maximum 37 
                            #voices in the topology report. However, Contiki often keep the packetbuf smaller than 127 bytes. So we may want to set an arbitrary value
    MAX_PATH_LENGTH = 40 # maximum number of hops before dropping the packet
    CLEANUP_INTERVAL = 15 #cleanup the routing table from expired entries every 15 seconds
    ALWAYS_INVALID_AGE = -1 # time 0. Route having this age are always invalid.
                            #In the C implementation it has value zero, but in the DES the time 0 actually exists so we need a smaller value
    ENTRY_EXPIRATION_TIME = 60
    TREE_BEACON_INTERVAL = 60
    SUBTREE_REPORT_OFFEST = TREE_BEACON_INTERVAL / 3
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



    def __init__(self, host: "StaticNode", sink: bool = False):
        Layer.__init__(self, host = host)
        Entity.__init__(self)
        self.sink = sink
        self.nbr_tbl: Dict[bytes, TARP.TARPRoute] = {} # routing table. key: linkaddr, value: TarpRoute record

        #TARP state
        _metric = float('inf')
        self.seqn = 0
        self.hops = TARP.MAX_PATH_LENGTH + 1
        self.tpl_buf: Dict[bytes, TARP.RouteStatus] = {} #topology diff buffer
        self.tpl_buf_offset # offset to be kept between one fragment and another

        rng_id = f"NODE:{self.host.id}/NET_TARP"
        self.host.context.random_manager.create_stream(rng_id)
        self.rng = self.host.context.random_manager.get_stream(rng_id)
        
        self._bootstrap_TARP() # bootstrap the protocol



    def _bootstrap_TARP(self):
        if self.sink: # if the sink, init your status and schedule the first beaocn
            _metric = 0
            self.hops = 0
            send_beacon_time = self.host.context.scheduler.now() + 1 # send a beaacon after one second 
            send_beacon_event = NetBeaconSendEvent(time=send_beacon_time, blame=self, callback=self._beacon_timer_cb)
            self.host.context.scheduler.schedule(send_beacon_event)

        cleanup_time = self.host.context.scheduler.now() + TARP.CLEANUP_INTERVAL
        cleanup_event = NetRoutingTableCleanupEvent(time = cleanup_time, blame = self, callback=self._nbr_tbl_cleanup_cb)
        self.host.context.scheduler.schedule(cleanup_event) #schedule first cleanup

    def _flush_tpl_buf(self): #flushes the diff buffer
        self.tpl_buf.clear()
        self.tpl_buf_offset = 0


    def _reset_connection_status(self, seqn: int):
        '''resets the protocol status when a beacon with higher seqnum is received'''
        for entry in self.nbr_tbl.values(): 
            if entry.type == NodeType.NODE_DESCENTANT: #make descendants old enough to be removed (sounds very bad, but is necessary)
                entry.age = TARP.ALWAYS_INVALID_AGE
            elif entry.type == NodeType.NODE_CHILD or entry.type == NodeType.NODE_PARENT: #downgrade all the other entries to neighbors
                entry.type = NodeType.NODE_NEIGHBOR

        self.parent = None
        _metric = 0 if self.sink else float('inf')
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

        broadcast_header = TARPBroadcastHeader(seqn=self.seqn, metric_q124=_metric, hops=self.hops, parent=self.parent)
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
                etx = _etx_est_rssi(rssi),
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

        if _preferred(new_metric, _metric): # if metric from this transmitter is better, st it as a parent
            self.parent = tx_addr
            _metric = new_metric
            self.hops = header.hops + 1

            #promote entry to parent
            tx_entry.type = NodeType.NODE_PARENT

            #schedule beacon forward
            beacon_forward_jitter = self.rng.uniform(low=0, high= 0.125) #random jitter for beacon forward
            beacon_forward_time  = current_time + TARP.TREE_BEACON_FORWARD_DELAY + beacon_forward_jitter
            beacon_forward_event = NetBeaconSendEvent(time=beacon_forward_time, blame=self, callback=self._beacon_timer_cb)
            self.host.context.scheduler.schedule(beacon_forward_event)

            #schedule first topology report
            first_report_time = current_time + self._subtree_report_base_delay_and_jitter()
            first_report_event = NetTopologyReportSendEvent(time = first_report_time, blame=self, callback=self._subtree_report_cb)
            self.host.context.scheduler.schedule(first_report_event)

        else: 
            '''
            Either the transmitter is a neighbor with a worse metric, or it is a child that is forwarding its beacon.
            If it is a child, then it has to be added to the buffer if it is still advertising this node as
            a parent, otherwise it has to be removed from the buffer, because it found a better parent.
            '''
            if header.parent == self.host.linkaddr: #if the transmitter is indicating this node as parent, then is this node's child
                tx_entry.type = NodeType.NODE_CHILD
                self.tpl_buf[tx_addr] = self.RouteStatus.STATUS_ADD # add it to the topology buffer
            else: # either it is a neighbor, or an old child
                if tx_entry.type == NodeType.NODE_CHILD:
                    tx_entry.type = NodeType.NODE_NEIGHBOR # downclass to neighobr
                    #if it was in the buffer, remove it
                    if tx_addr in self.tpl_buf:
                        self.tpl_buf.pop(tx_addr)
                #else it is a neighbor: no need to do anything, entry type is already up to date
    


    def _subtree_report_cb(self): #TODO: check tis function

        if len(self.tpl_buf) == 0: # if the topology buffer is empty, just send a keep alive and schedule next report
            # NOTE: in the original C code, there is a bug: in this case, the report is not sent, but when I designed the protocol
            # in this case the report actually MUST be sent, because it serves as keep alive message.
            # So, here we implement it
            self._schedule_next_report()

            header = TARPUnicastHeader(type=TARPUnicastType.UC_TYPE_REPORT, s_addr=self.host.linkaddr, d_addr=self.parent, hops=0)
            packet = TARPPacket(header=header, APDU=None)
            self.host.mac.send(packet, self.parent, self._uc_sent)

        
        else: # the buffer is not empty, handle fragmentation and sending.
            remaining_items = len(self.tpl_buf) - self.tpl_buf_offset
            frag_size = min(remaining_items, TARP.MAX_STAT_PER_FRAGMENT)

            # build payload for this fragment
            voice_addr = list(self.tpl_buf.keys())
            #extract a sub-dictionary corresponding to this fragment
            fragment_payload = {addr: self.tpl_buf[addr] for addr in voice_addr[self.tpl_buf_offset : self.tpl_buf_offset + frag_size]}
        

            header = TARPUnicastHeader(type=TARPUnicastType.UC_TYPE_REPORT, s_addr=self.host.linkaddr, d_addr=self.parent, hops=0)
            packet = TARPPacket(header=header, APDU=fragment_payload)
            self.host.mac.send(packet, self.parent, self._uc_sent)

            # move the offset for the next fragment.
            self.tpl_buf_offset += frag_size

            # if there are more fragments to be sent, schedule the next one with a short delay.
            if self.tpl_buf_offset < len(self.tpl_buf):
                # schedule the next fragment with a short inter-packet delay.
                next_frag_time = self.host.context.scheduler.now() + 0.02 # 20ms delay
                next_report_event = NetTopologyReportSendEvent(time=next_frag_time, blame=self, callback=self._subtree_report_cb)
                self.host.context.scheduler.schedule(next_report_event)
            else:
                # the entire buffer has been transmitted, flush and schedule next topology report
                self._flush_tpl_buf()
                self._schedule_next_report()


                
    def _schedule_next_report(self):
        interval = self._subtree_report_node_interval()
        next_report_time = self.host.context.scheduler.now() + interval
        self.host.context.scheduler.schedule(NetTopologyReportSendEvent(time=next_report_time, blame=self, callback=self._subtree_report_cb))



    def _buff_subtree(self):
        '''fills the buffer with the subtree, to send to the new parent'''
        self._flush_tpl_buf() #flush the buffer
        for addr, entry in self.nbr_tbl.items():
            if entry.type ==  NodeType.NODE_CHILD or entry.type == NodeType.NODE_DESCENTANT:
                self.tpl_buf[addr] = self.RouteStatus.STATUS_ADD

    def _change_parent(self):
        best_metric = float('inf')
        new_parent_addr = None

        #find neighbor with best metric (excluding descendants and children)
        for addr, entry in self.nbr_tbl.items():
           if entry.type == NodeType.NODE_NEIGHBOR:
               metric = self._metric(entry.adv_metric, entry.etx)
               if metric < best_metric:
                   best_metric = metric
                   new_parent_addr = addr

        old_parent_entry = self.nbr_tbl[self.parent]
        old_parent_entry.type = NodeType.NODE_NEIGHBOR
        old_parent_entry.age = TARP.ALWAYS_INVALID_AGE

        if new_parent_addr: # if a new parent has been found
            self.parent = new_parent_addr
            _metric = best_metric
            self.nbr_tbl[new_parent_addr].type = NodeType.NODE_PARENT
            self.hops = self.nbr_tbl[new_parent_addr] + 1

            self._buff_subtree() # bufferize the subtree
            self._subtree_report_cb() #send the buffer to the new parent

        else: # there are no neighbors available, disconnect from the network
            self.parent = None
            self.hops = TARP.MAX_PATH_LENGTH + 1 # NOTE: not present in rp.c



    def _uc_recv(self, payload: TARPPacket, tx_addr: bytes):

        header: TARPUnicastHeader = payload.header
        header.hops = header.hops + 1 #update hop counts in the header to reuse it in case of forward

        if header.hops > TARP.MAX_PATH_LENGTH: #drop packets with too many hops
            return
        
        self._nbr_tbl_refresh(tx_addr)

        if header.type == TARPUnicastType.UC_TYPE_DATA:
            if header.d_addr == self.host.linkaddr:
                self.host.app.receive(payload.APDU) #deliver to application
            else:
                self._forward_data(header, payload=payload.APDU)

        elif header.type == TARPUnicastType.UC_TYPE_REPORT:
            net_buf =  payload.APDU #dictionary of report voices incoming from the network
            self._nbr_tbl_update(tx_addr= tx_addr, buf = net_buf)
            #if not the sink, schedule the next report pigggybacking also local information, otherwsie flush the buffer
            if not self.sink:
                self._schedule_next_report() 
            else:
                self._flush_tpl_buf()




    def _uc_sent(self, rx_addr: bytes, status_ok: bool, num_tx: int):
        '''this function updates the metric based on the transmission result'''
        self.nbr_tbl[rx_addr].num_tx += 1 # increment transmissions number

        if status_ok:
            self.nbr_tbl[rx_addr].num_ack += 1
            self.nbr_tbl[rx_addr].etx = _etx_update(num_tx=self.nbr_tbl[rx_addr].num_tx,
                                                    num_ack=self.nbr_tbl[rx_addr].num_ack,
                                                    o_etx=self.nbr_tbl[rx_addr].etx,
                                                    rssi=self.host.mac.get_last_packet_rssi()
                                                    )
            self._nbr_tbl_refresh(rx_addr) # refresh entry
        if not status_ok:
            self.nbr_tbl[rx_addr] = TARP.ALWAYS_INVALID_AGE
            self._nbr_tbl_cleanup_cb() # cleanup table



            




    def receive(self, payload: TARPPacket, tx_addr: bytes):
        #first, understand if it is a broadcast or unicast, and then delegate to specific functions
        # in Contiki the incoming packet is dispatched to the correct function by lower layers
        if isinstance(payload.header, TARPUnicastHeader):
            self._uc_recv(payload, tx_addr)
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

    def _nbr_tbl_update(self, tx_addr: bytes, buf: Dict[bytes, "TARP.RouteStatus"]):
        tx_entry = self.nbr_tbl[tx_addr]
        if tx_entry and tx_entry.type == NodeType.NODE_NEIGHBOR: # if it is a neighbor that chose this node as parent, book the change into the buffer
            self.tpl_buf[tx_addr] = TARP.RouteStatus.STATUS_ADD
            tx_entry.adv_metric = float('inf') #set infinite metric to avoid looès
            tx_entry.type == NodeType.NODE_CHILD # NOTE: not present in rp.c
        #else it is an already known child

       # update the routing table and the local buffer with the info contained in the topology report
        for d_addr, d_status in buf.items():
            #NOTE: here there is a check to skip entries if the neighbor table is full (due to RAM constraint), here we dont consider it
            self.tpl_buf[d_addr] = d_status

            if d_status == TARP.RouteStatus.STATUS_ADD: # add descendant in the neighbor table
                d_entry = TARP.TARPRoute(type = NodeType.NODE_DESCENTANT,
                                         adv_metric=float('inf'),
                                         age=TARP.ALWAYS_INVALID_AGE,
                                         hops= TARP.MAX_PATH_LENGTH+1,
                                         nexthop=tx_addr)
                self.nbr_tbl[d_addr] = d_entry

            elif d_status == TARP.RouteStatus.STATUS_REMOVE:
                self.nbr_tbl.pop(d_addr)
                



    def _nbr_tbl_cleanup_cb(self):
        current_time = self.host.context.scheduler.now()
        expired_addr = [addr for addr, route in self.nbr_tbl.items() if not _valid(current_time=current_time, route=route) and route.type != NodeType.NODE_DESCENTANT]

        parent_change = False
        #remove expired keys
        for addr in expired_addr:
            if self.nbr_tbl[addr].type == NodeType.NODE_CHILD:
                self._remove_subtree(addr)
            elif self.nbr_tbl[addr].type == NodeType.NODE_PARENT:
                parent_change = True
                self.parent = None
            else:
                self.nbr_tbl.pop(addr)

        cleanup_time = self.host.context.scheduler.now() + TARP.CLEANUP_INTERVAL
        cleanup_event = NetRoutingTableCleanupEvent(time = cleanup_time, blame = self, callback=self._nbr_tbl_cleanup_cb)
        self.host.context.scheduler.schedule(cleanup_event) #schedule next cleanup

        if parent_change:
            self._change_parent()
            
        

    def _remove_subtree(self, child_addr: bytes):
        subtree_addr = [addr for addr, route in self.nbr_tbl.items() if route.nexthop == child_addr] # subtree entries
        for addr in subtree_addr: #remove entries from neighbor table
            self.nbr_tbl.pop(addr)

        self.tpl_buf.update({c_addr: TARP.RouteStatus.STATUS_REMOVE for c_addr in subtree_addr}) # update topology diff buffer
  
    
    def _subtree_report_base_delay_and_jitter(self) -> float:
        return (5 / self.hops) + (self.rng(low=0, hig=0.4))
    
    def _subtree_report_node_interval(self) -> float:
        return TARP.SUBTREE_REPORT_OFFEST * (1.0 + (1.0/self.hops))



