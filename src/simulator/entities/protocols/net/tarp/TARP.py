# SPE-project/src/simulator/entities/protocols/net/tarp/TARP.py

from simulator.entities.protocols.common.Layer import Layer
from simulator.entities.common.Entity import Entity
from simulator.engine.random import RandomGenerator
from simulator.entities.protocols.common.packets import (
    Frame_802154,
    TARPPacket,
    TARPUnicastHeader,
    TARPBroadcastHeader,
    TARPUnicastType,
)
from simulator.entities.protocols.net.common.net_events import (
    NetBeaconSendEvent,
    NetRoutingTableCleanupEvent,
    NetTopologyReportSendEvent,
)
from typing import Dict, Any, Optional, TYPE_CHECKING

# Local TARP-specific imports
from .tarp_structures import TARPRoute, NodeType, RouteStatus
from . import tarp_utils

if TYPE_CHECKING:
    from simulator.entities.physical.devices.nodes import StaticNode

"""
This class implements TARP (Tree-based Any-to-any Routing Protocol).
It follows exactly the implementation of the C source code (readapted in pythonic
way and avoiding some C specific coding paradigm, obviously).
source:  https://github.com/DaMole98/LPWN-project2/tree/main
"""

class TARP(Layer, Entity):
    """
    This class implements TARP (Tree-based Any-to-any Routing Protocol).
    """

    MAX_STAT_PER_FRAGMENT = 37
    MAX_PATH_LENGTH = 40
    CLEANUP_INTERVAL = 15
    ALWAYS_VALID_AGE = float("inf")
    ALWAYS_INVALID_AGE = -1
    ENTRY_EXPIRATION_TIME = 600
    TREE_BEACON_INTERVAL = 60
    SUBTREE_REPORT_OFFEST = TREE_BEACON_INTERVAL / 3
    RSSI_LOW_THR = -85
    RSSI_HIGH_REF = -35
    DELTA_ETX_MIN = 0.3
    THR_H = 100
    ALPHA = 0.9
    TREE_BEACON_FORWARD_DELAY = 1 / 10

    # Redefine for easy access within the class scope
    TARPRoute = TARPRoute
    NodeType = NodeType
    RouteStatus = RouteStatus


    def __init__(self, host: "StaticNode", sink: bool = False):
        Layer.__init__(self, host=host)
        Entity.__init__(self)
        self.sink = sink
        self.parent = None
        self.nbr_tbl: Dict[bytes, TARP.TARPRoute] = {}

        self.metric = float("inf")
        self.seqn = 0
        self.hops = TARP.MAX_PATH_LENGTH + 1
        self.tpl_buf: Dict[bytes, TARP.RouteStatus] = {}
        self.tpl_buf_offset = 0

        self._cleanup_timer = None

        rng_id = f"NODE:{self.host.id}/NET_TARP"
        self.rng = RandomGenerator(
            random_manager=self.host.context.random_manager,
            stream_key=rng_id,
        )

        self._bootstrap_TARP()

    def _bootstrap_TARP(self):
        if self.sink:
            self.metric = 0
            self.hops = 0
            send_beacon_time = self.host.context.scheduler.now() + 1
            send_beacon_event = NetBeaconSendEvent(
                time=send_beacon_time, blame=self, callback=self._beacon_timer_cb
            )
            self.host.context.scheduler.schedule(send_beacon_event)

        self._reschedule_cleanup()

    def _flush_tpl_buf(self):
        self.tpl_buf.clear()
        self.tpl_buf_offset = 0

    def _reset_connection_status(self, seqn: int):
        for entry in self.nbr_tbl.values():
            if entry.type == self.NodeType.NODE_DESCENTANT:
                entry.age = self.ALWAYS_INVALID_AGE
            elif (
                entry.type == self.NodeType.NODE_CHILD or entry.type == self.NodeType.NODE_PARENT
            ):
                entry.type = self.NodeType.NODE_NEIGHBOR

        self.parent = None
        self.metric = 0 if self.sink else float("inf")
        self.seqn = seqn
        self._flush_tpl_buf()

    def _reschedule_cleanup(self):
        if self._cleanup_timer:
            self.host.context.scheduler.unschedule(self._cleanup_timer)

        cleanup_time = self.host.context.scheduler.now() + self.CLEANUP_INTERVAL
        self._cleanup_timer = NetRoutingTableCleanupEvent(
            time=cleanup_time,
            blame=self,
            descriptor=f"Node:{self.host.id}",
            callback=self._nbr_tbl_cleanup_cb,
        )
        self.host.context.scheduler.schedule(self._cleanup_timer)

    def send(self, payload: Any, destination: Optional[bytes] = None) -> bool:
        if not self.sink and self.parent is None:
            return False

        nexthop = self._nbr_tbl_lookup(destination)
        if nexthop is None:
            print(
                f"[{self.host.context.scheduler.now():.6f}s] [{self.host.id}] [TARP/SEND] "
                f"No route to destination {destination.hex()}. Dropping packet.",
                flush=True,
            )
            return False

        packet_header = TARPUnicastHeader(
            type=TARPUnicastType.UC_TYPE_DATA,
            s_addr=self.host.linkaddr,
            d_addr=destination,
            hops=0,
        )
        net_packet = TARPPacket(header=packet_header, APDU=payload)
        self.host.mac.send(payload=net_packet, destination=nexthop)
        return True

    def _forward_data(self, header: TARPUnicastHeader, payload: Any):
        nexthop = self._nbr_tbl_lookup(header.d_addr)
        if nexthop is None:
            print(
                f"[{self.host.context.scheduler.now():.6f}s] [{self.host.id}] [TARP/FORWARD] "
                f"No route to destination {header.d_addr.hex()}. Dropping packet.",
                flush=True,
            )
            return False

        net_packet = TARPPacket(header=header, APDU=payload)
        self.host.mac.send(payload=net_packet, destination=nexthop)
        return True

    def _beacon_timer_cb(self):
        print(
            f"DEBUG [{self.host.context.scheduler.now():.6f}s] [{self.host.id}]: _beacon_timer_cb EXECUTED."
        )

        if self.sink:
            new_seqn = self.seqn + 1
            self._reset_connection_status(new_seqn)
            next_beacon_time = (
                self.host.context.scheduler.now() + self.TREE_BEACON_INTERVAL
            )
            next_beacon_event = NetBeaconSendEvent(
                time=next_beacon_time, blame=self, callback=self._beacon_timer_cb
            )
            self.host.context.scheduler.schedule(next_beacon_event)

        broadcast_header = TARPBroadcastHeader(
            epoch=self.seqn, metric_q124=self.metric, hops=self.hops, parent=self.parent
        )
        self._broadcast_send(broadcast_header, data=None)


    def _bc_recv(self, payload: TARPPacket, tx_addr: bytes, rssi: float):
        #rssi = self.host.mac.get_last_packet_rssi()
        #rssi = self.host.phy.get_last_rssi()

        if rssi < self.RSSI_LOW_THR:
            print(f"DEBUG [{self.host.context.scheduler.now():.6f}s] [{self.host.id}] "
              f"Beacon from {tx_addr.hex()} ignored, RSSI too low ({rssi:.2f} < {self.RSSI_LOW_THR}).")
            return

        header: TARPBroadcastHeader = payload.header
        current_time = self.host.context.scheduler.now()

        print(
            f"DEBUG [{current_time:.6f}s] [{self.host.id}]: Received beacon from {tx_addr.hex()} with epoch {header.epoch}. My epoch is {self.seqn}."
        )

        tx_entry = self.nbr_tbl.get(tx_addr)

        if tx_entry:
            self._nbr_tbl_refresh(addr=tx_addr)
            tx_entry.adv_metric = header.metric_q124
        else:
            tx_entry = self.TARPRoute(
                type=self.NodeType.NODE_NEIGHBOR,
                age=current_time,
                nexthop=tx_addr,
                hops=header.hops,
                etx=tarp_utils._etx_est_rssi(rssi, self.RSSI_HIGH_REF, self.RSSI_LOW_THR),
                num_tx=0,
                num_ack=0,
                adv_metric=header.metric_q124,
            )
            self.nbr_tbl[tx_addr] = tx_entry

        if not self.sink and header.epoch > self.seqn:
            self._reset_connection_status(header.epoch)

        new_metric = tarp_utils._metric(header.metric_q124, tx_entry.etx)
        is_preferred = tarp_utils._preferred(new_metric, self.metric, self.THR_H, self.DELTA_ETX_MIN)


        print(f"DEBUG [{self.host.context.scheduler.now():.6f}s] [{self.host.id}] "
          f"Parent Selection Logic: Beacon from {tx_addr.hex()}. "
          f"My current metric: {self.metric:.4f}. "
          f"Beacon metric: {header.metric_q124:.4f}. "
          f"Link ETX: {tx_entry.etx:.4f}. "
          f"New potential metric: {new_metric:.4f}. "
          f"Is Preferred? -> {is_preferred}")

        if is_preferred:
            self.parent = tx_addr
            self.metric = new_metric
            self.hops = header.hops + 1
            tx_entry.type = self.NodeType.NODE_PARENT
            print(
                f"[{self.host.context.scheduler.now():.6f}s] [{self.host.id}] [TARP/BC_RECV] "
                f"SELECTING NEW PARENT {tx_addr.hex()}.",
                flush=True,
            )

            beacon_forward_jitter = self.rng.uniform(low=0, high=0.125)
            beacon_forward_time = (
                current_time + self.TREE_BEACON_FORWARD_DELAY + beacon_forward_jitter
            )
            beacon_forward_event = NetBeaconSendEvent(
                time=beacon_forward_time, blame=self, callback=self._beacon_timer_cb
            )
            self.host.context.scheduler.schedule(beacon_forward_event)

            first_report_time = (
                current_time + self._subtree_report_base_delay_and_jitter()
            )
            first_report_event = NetTopologyReportSendEvent(
                time=first_report_time, blame=self, callback=self._subtree_report_cb
            )
            self.host.context.scheduler.schedule(first_report_event)
        else:
            if header.parent == self.host.linkaddr:
                tx_entry.type = self.NodeType.NODE_CHILD
                self.tpl_buf[tx_addr] = self.RouteStatus.STATUS_ADD
            else:
                if tx_entry.type == self.NodeType.NODE_CHILD:
                    tx_entry.type = self.NodeType.NODE_NEIGHBOR
                    if tx_addr in self.tpl_buf:
                        self.tpl_buf.pop(tx_addr)

    def _subtree_report_cb(self):
        if not self.tpl_buf:
            self._schedule_next_report()
            header = TARPUnicastHeader(
                type=TARPUnicastType.UC_TYPE_REPORT,
                s_addr=self.host.linkaddr,
                d_addr=self.parent,
                hops=0,
            )
            packet = TARPPacket(header=header, APDU={})
            self.host.mac.send(packet, self.parent)
        else:
            remaining_items = len(self.tpl_buf) - self.tpl_buf_offset
            frag_size = min(remaining_items, self.MAX_STAT_PER_FRAGMENT)
            voice_addr = list(self.tpl_buf.keys())
            fragment_payload = {
                addr: self.tpl_buf[addr]
                for addr in voice_addr[self.tpl_buf_offset : self.tpl_buf_offset + frag_size]
            }
            header = TARPUnicastHeader(
                type=TARPUnicastType.UC_TYPE_REPORT,
                s_addr=self.host.linkaddr,
                d_addr=self.parent,
                hops=0,
            )
            packet = TARPPacket(header=header, APDU=fragment_payload)
            self.host.mac.send(packet, self.parent)
            self.tpl_buf_offset += frag_size
            if self.tpl_buf_offset < len(self.tpl_buf):
                next_frag_time = self.host.context.scheduler.now() + 0.02
                next_report_event = NetTopologyReportSendEvent(
                    time=next_frag_time, blame=self, callback=self._subtree_report_cb
                )
                self.host.context.scheduler.schedule(next_report_event)
            else:
                self._flush_tpl_buf()
                self._schedule_next_report()

    def _schedule_next_report(self):
        interval = self._subtree_report_node_interval()
        next_report_time = self.host.context.scheduler.now() + interval
        self.host.context.scheduler.schedule(
            NetTopologyReportSendEvent(
                time=next_report_time, blame=self, callback=self._subtree_report_cb
            )
        )

    def _buff_subtree(self):
        self._flush_tpl_buf()
        for addr, entry in self.nbr_tbl.items():
            if (
                entry.type == self.NodeType.NODE_CHILD
                or entry.type == self.NodeType.NODE_DESCENTANT
            ):
                self.tpl_buf[addr] = self.RouteStatus.STATUS_ADD

    def _change_parent(self, old_parent_addr: bytes):
        best_metric = float("inf")
        new_parent_addr = None

        for addr, entry in self.nbr_tbl.items():
            if entry.type == self.NodeType.NODE_NEIGHBOR:
                metric = tarp_utils._metric(entry.adv_metric, entry.etx)
                if metric < best_metric:
                    best_metric = metric
                    new_parent_addr = addr

        old_parent_entry = self.nbr_tbl[old_parent_addr]
        old_parent_entry.type = self.NodeType.NODE_NEIGHBOR
        old_parent_entry.age = self.ALWAYS_INVALID_AGE

        if new_parent_addr:
            self.parent = new_parent_addr
            self.metric = best_metric
            self.nbr_tbl[new_parent_addr].type = self.NodeType.NODE_PARENT
            self.hops = self.nbr_tbl[new_parent_addr].hops + 1
            self._buff_subtree()
            self._subtree_report_cb()
        else:
            self.parent = None
            self.hops = self.MAX_PATH_LENGTH + 1

        print(
            f"[{self.host.context.scheduler.now():.6f}s] [{self.host.id}] [TARP/CHANGE_PARENT] "
            f"SELECTING NEW PARENT {new_parent_addr.hex() if new_parent_addr else None}.",
            flush=True,
        )

    def _uc_recv(self, payload: TARPPacket, tx_addr: bytes):
        if tx_addr not in self.nbr_tbl:
            return

        header: TARPUnicastHeader = payload.header
        header.hops += 1

        if header.hops > self.MAX_PATH_LENGTH:
            return

        self._nbr_tbl_refresh(tx_addr)

        if header.type == TARPUnicastType.UC_TYPE_DATA:
            if header.d_addr == self.host.linkaddr:
                self.host.app.receive(payload.APDU, sender_addr=tx_addr)
            else:
                self._forward_data(header, payload=payload.APDU)
        elif header.type == TARPUnicastType.UC_TYPE_REPORT:
            net_buf = payload.APDU
            self._nbr_tbl_update(tx_addr=tx_addr, buf=net_buf)
            if not self.sink:
                self._schedule_next_report()
            else:
                self._flush_tpl_buf()


    def _uc_sent(self, rx_addr: bytes, status_ok: bool, num_tx: int, ack_rssi: float):
        if rx_addr is None or rx_addr not in self.nbr_tbl:
            return

        route = self.nbr_tbl[rx_addr]
        route.num_tx += num_tx

        if status_ok:
            route.num_ack += 1
            route.etx = tarp_utils._etx_update(
                num_tx=route.num_tx,
                num_ack=route.num_ack,
                o_etx=route.etx,
                rssi=ack_rssi,
                alpha=self.ALPHA,
                rssi_high_ref=self.RSSI_HIGH_REF,
                rssi_low_thr=self.RSSI_LOW_THR,
            )
            self._nbr_tbl_refresh(rx_addr)
        else:
            route.age = self.ALWAYS_INVALID_AGE
            self._do_cleanup()



    def receive(self, payload: TARPPacket, sender_addr: bytes, rssi: float):
        print(f">>> DEBUG-NET [{self.host.id}]: receive() called with RSSI = {rssi:.2f} dBm")

        if isinstance(payload.header, TARPUnicastHeader):
            self._uc_recv(payload, sender_addr)
        elif isinstance(payload.header, TARPBroadcastHeader):
            self._bc_recv(payload, sender_addr, rssi=rssi)

    def _broadcast_send(self, header: TARPBroadcastHeader, data: Optional[Any] = None):
        broadcast_packet = TARPPacket(header=header, APDU=data)
        b_addr = Frame_802154.broadcast_linkaddr
        self.host.mac.send(payload=broadcast_packet, destination=b_addr)

    def _nbr_tbl_lookup(self, dst_addr: bytes) -> bytes:
        nexthop = self.parent
        if dst_addr in self.nbr_tbl:
            nexthop = self.nbr_tbl[dst_addr].nexthop
        return nexthop

    def _nbr_tbl_refresh(self, addr: bytes):
        if addr in self.nbr_tbl:
            self.nbr_tbl[addr].age = self.host.context.scheduler.now()

    def _nbr_tbl_update(self, tx_addr: bytes, buf: Dict[bytes, "TARP.RouteStatus"]):
        tx_entry = self.nbr_tbl.get(tx_addr)
        if tx_entry and tx_entry.type == self.NodeType.NODE_NEIGHBOR:
            self.tpl_buf[tx_addr] = self.RouteStatus.STATUS_ADD
            tx_entry.adv_metric = float("inf")
            tx_entry.type = self.NodeType.NODE_CHILD

        for d_addr, d_status in buf.items():
            self.tpl_buf[d_addr] = d_status
            if d_status == self.RouteStatus.STATUS_ADD:
                d_entry = self.TARPRoute(
                    type=self.NodeType.NODE_DESCENTANT,
                    adv_metric=float("inf"),
                    age=self.ALWAYS_VALID_AGE,
                    hops=self.MAX_PATH_LENGTH + 1,
                    nexthop=tx_addr,
                    etx=0.0,
                    num_tx=0,
                    num_ack=0,
                )
                self.nbr_tbl[d_addr] = d_entry
            elif d_status == self.RouteStatus.STATUS_REMOVE:
                if d_addr in self.nbr_tbl:
                    self.nbr_tbl.pop(d_addr)

    def _do_cleanup(self):
        current_time = self.host.context.scheduler.now()
        expired_addr = [
            addr
            for addr, route in self.nbr_tbl.items()
            if not tarp_utils._valid(current_time, route, self.ENTRY_EXPIRATION_TIME)
            and route.type != self.NodeType.NODE_DESCENTANT
        ]

        parent_to_change = None
        for addr in expired_addr:
            if self.nbr_tbl[addr].type == self.NodeType.NODE_CHILD:
                self._remove_subtree(addr)
            elif self.nbr_tbl[addr].type == self.NodeType.NODE_PARENT:
                parent_to_change = self.parent
                self.parent = None
            
            if addr in self.nbr_tbl:
                 self.nbr_tbl.pop(addr)

        if parent_to_change:
            self._change_parent(old_parent_addr=parent_to_change)

    def _nbr_tbl_cleanup_cb(self):
        self._do_cleanup()
        self._reschedule_cleanup()

    def _remove_subtree(self, child_addr: bytes):
        subtree_addr = [
            addr for addr, route in self.nbr_tbl.items() if route.nexthop == child_addr
        ]
        for addr in subtree_addr:
            if addr in self.nbr_tbl:
                self.nbr_tbl.pop(addr)
        
        self.tpl_buf.update(
            {c_addr: self.RouteStatus.STATUS_REMOVE for c_addr in subtree_addr}
        )

    def _subtree_report_base_delay_and_jitter(self) -> float:
        return (5 / self.hops) + (self.rng.uniform(low=0, high=0.4))

    def _subtree_report_node_interval(self) -> float:
        return self.SUBTREE_REPORT_OFFEST * (1.0 + (1.0 / self.hops))