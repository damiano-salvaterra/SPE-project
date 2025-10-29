from simulator.entities.protocols.common.Layer import Layer
from simulator.entities.common import Entity
from simulator.engine.random import RandomGenerator
from simulator.entities.protocols.common.packets import (
    Frame_802_15_4,
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
from typing import Dict, Any, Optional

# Local TARP-specific imports
from simulator.entities.protocols.net.tarp.tarp_structures import (
    TARPRoute,
    NodeType,
    RouteStatus,
)
from simulator.entities.protocols.net.tarp import tarp_utils
from simulator.entities.protocols.net.tarp.parameters import TARPParameters
from evaluation.signals.tarp_signals import (
    TARPForwardingSignal,
    TARPReceiveSignal,
)

from simulator.entities.common import NetworkNode

"""
This class implements TARP (Tree-based Any-to-any Routing Protocol).
It is a Python port of the original C implementation, aiming to replicate
the core logic for timers, route management, and topology discovery.
Reference C source: https://github.com/DaMole98/LPWN-project2/tree/main
"""


class TARPProtocol(Layer, Entity):
    """
    This class implements TARP (Tree-based Any-to-any Routing Protocol).
    """

    # Redefine for easy access within the class scope
    TARPRoute = TARPRoute
    NodeType = NodeType
    RouteStatus = RouteStatus

    def __init__(self, host: NetworkNode, sink: bool = False):
        Layer.__init__(self, host=host)
        Entity.__init__(self)
        self.sink = sink
        self.parent: Optional[bytes] = None
        self.nbr_tbl: Dict[bytes, TARPProtocol.TARPRoute] = {}

        self.metric = 0.0 if self.sink else float("inf")
        self.seqn = 0
        self.hops = 0 if self.sink else TARPParameters.MAX_PATH_LENGTH + 1

        # Buffer for outgoing topology reports
        self.tpl_buf: Dict[bytes, TARPProtocol.RouteStatus] = {}
        self.tpl_buf_offset = 0

        self._cleanup_timer: Optional[NetRoutingTableCleanupEvent] = None
        self._report_timer: Optional[NetTopologyReportSendEvent] = None
        self._beacon_timer: Optional[NetBeaconSendEvent] = None

        # Random Number Generator for this protocol instance
        rng_id = f"NODE:{self.host.id}/NET_TARP"
        self.rng = RandomGenerator(
            random_manager=self.host.context.random_manager,
            stream_key=rng_id,
        )

        self._bootstrap_TARP()

    def _bootstrap_TARP(self):
        """Initializes the protocol timers."""
        if self.sink:
            # The sink starts the beaconing process
            initial_beacon_time = self.host.context.scheduler.now() + 1
            self._beacon_timer = NetBeaconSendEvent(
                time=initial_beacon_time, blame=self, callback=self._beacon_timer_cb
            )
            self.host.context.scheduler.schedule(self._beacon_timer)

        self._reschedule_cleanup()

    # --- Timer and Delay Helper Methods (replicating C logic) ---

    def _get_beacon_forward_delay(self) -> float:
        """
        Calculates the delay for forwarding a beacon with jitter,
        replicating: TREE_BEACON_FORWARD_DELAY + (random_rand() % TREE_BEACON_FORWARD_DELAY)
        """
        base_delay = TARPParameters.TREE_BEACON_FORWARD_DELAY
        jitter = self.rng.uniform(low=0, high=base_delay)
        return base_delay + jitter

    def _get_next_report_interval(self) -> float:
        """
        Calculates the interval for the next topology report,
        replicating: SUBTREE_REPORT_INTERVAL * (1 + 1/hops) + random_jitter
        """
        if self.hops <= 0:  # Should only happen for the sink, which doesn't report
            return TARPParameters.SUBTREE_REPORT_OFFEST

        base_interval = TARPParameters.SUBTREE_REPORT_OFFEST * (1.0 + (1.0 / self.hops))

        # Random jitter up to half of the base report interval
        max_jitter = TARPParameters.SUBTREE_REPORT_OFFEST / 2
        jitter = self.rng.uniform(low=0, high=max_jitter)

        return base_interval + jitter

    # --- Core Protocol Logic ---

    def _flush_tpl_buf(self):
        """Clears the topology report buffer."""
        self.tpl_buf.clear()
        self.tpl_buf_offset = 0

    def _reset_connection_status(self, seqn: int):
        """Resets the node's routing state upon detecting a new epoch."""
        for entry in self.nbr_tbl.values():
            if entry.type == self.NodeType.NODE_DESCENTANT:
                entry.age = TARPParameters.ALWAYS_INVALID_AGE
            elif (
                entry.type == self.NodeType.NODE_CHILD
                or entry.type == self.NodeType.NODE_PARENT
            ):
                entry.type = self.NodeType.NODE_NEIGHBOR

        self.parent = None
        self.metric = 0 if self.sink else float("inf")
        self.hops = 0 if self.sink else TARPParameters.MAX_PATH_LENGTH + 1
        self.seqn = seqn
        self._flush_tpl_buf()

        # Stop scheduled timers to prevent outdated actions
        if self._beacon_timer and not self._beacon_timer._cancelled:
            self.host.context.scheduler.unschedule(self._beacon_timer)
        if self._report_timer and not self._report_timer._cancelled:
            self.host.context.scheduler.unschedule(self._report_timer)

    '''
    def send(self, payload: Any, destination: Optional[bytes] = None) -> bool:
        """Sends an application data packet to a destination."""
        if not self.sink and self.parent is None:
            # Drop packet if we are disconnected from the tree
            if (
                self.host.context.scheduler.now()
                > 2 * TARPParameters.TREE_BEACON_INTERVAL
            ):
                print(
                    f"[{self.host.context.scheduler.now():.6f}s] [{self.host.id}] [TARP/SEND] "
                    f"No parent, cannot send. Dropping packet.",
                    flush=True,
                )
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
    '''

    #NOTE: check this function
    def send(self, payload: Any, destination: Optional[bytes] = None) -> bool:
        """Sends an application data packet to a destination."""
        # DEBUG: Log entry into TARP send function
        print(f"[DEBUG][{self.host.context.scheduler.now():.6f}s][{self.host.id}] TARPProtocol.send() CALLED. Destination: {destination.hex() if destination else 'None'}.")

        if not self.sink and self.parent is None:
            # DEBUG: Log packet drop due to no parent
            print(f"[DEBUG][{self.host.context.scheduler.now():.6f}s][{self.host.id}] TARP send: No parent, dropping packet.")
            if (
                self.host.context.scheduler.now()
                > 2 * TARPParameters.TREE_BEACON_INTERVAL
            ):
                print(
                    f"[{self.host.context.scheduler.now():.6f}s] [{self.host.id}] [TARP/SEND] "
                    f"No parent, cannot send. Dropping packet.",
                    flush=True,
                )
            return False

        # DEBUG: Log before neighbor table lookup
        print(f"[DEBUG][{self.host.context.scheduler.now():.6f}s][{self.host.id}] TARP send: Looking up nexthop for {destination.hex() if destination else 'None'}.")
        nexthop = self._nbr_tbl_lookup(destination)
         # DEBUG: Log result of neighbor table lookup
        print(f"[DEBUG][{self.host.context.scheduler.now():.6f}s][{self.host.id}] TARP send: Nexthop found: {nexthop.hex() if nexthop else 'None'}.")

        if nexthop is None:
            # DEBUG: Log packet drop due to no route
            print(f"[DEBUG][{self.host.context.scheduler.now():.6f}s][{self.host.id}] TARP send: No route found, dropping packet.")
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

        # DEBUG: Log before calling MAC send and wrap in try-except
        mac_send_success = False
        try:
            print(f"[DEBUG][{self.host.context.scheduler.now():.6f}s][{self.host.id}] TARP send: Calling self.host.mac.send() to nexthop {nexthop.hex()}.")
            # Note: Assuming mac.send doesn't return a boolean, adjust if it does
            self.host.mac.send(payload=net_packet, destination=nexthop)
            mac_send_success = True # Assume success if no exception
            print(f"[DEBUG][{self.host.context.scheduler.now():.6f}s][{self.host.id}] TARP send: Call to mac.send() completed.")
        except Exception as e:
            mac_send_success = False
            print(f"[DEBUG][{self.host.context.scheduler.now():.6f}s][{self.host.id}] TARP send: EXCEPTION during mac.send(): {e}")

        # DEBUG: Log final return value based on whether MAC call was attempted
        final_return_value = (nexthop is not None) # Simplistic: Return True if a nexthop was found, False otherwise
        print(f"[DEBUG][{self.host.context.scheduler.now():.6f}s][{self.host.id}] TARPProtocol.send() returning {final_return_value}.")
        return final_return_value # Returning True if a route was found, even if MAC fails later


    def _forward_data(self, header: TARPUnicastHeader, payload: Any):
        """Forwards a data packet towards its destination."""
        nexthop = self._nbr_tbl_lookup(header.d_addr)
        if nexthop is None:
            print(
                f"[{self.host.context.scheduler.now():.6f}s] [{self.host.id}] [TARP/FORWARD] "
                f"No route to destination {header.d_addr.hex()}. Dropping packet.",
                flush=True,
            )
            return

        net_packet = TARPPacket(header=header, APDU=payload)
        self.host.mac.send(payload=net_packet, destination=nexthop)

    def receive(self, payload: TARPPacket, sender_addr: bytes, rssi: float):
        """Handles incoming packets from the MAC layer."""
        if isinstance(payload.header, TARPUnicastHeader):
            self._uc_recv(payload, sender_addr)
        elif isinstance(payload.header, TARPBroadcastHeader):
            self._bc_recv(payload, sender_addr, rssi=rssi)

    def _bc_recv(self, payload: TARPPacket, tx_addr: bytes, rssi: float):
        """Handles a received broadcast (beacon) packet."""
        if rssi < TARPParameters.RSSI_LOW_THR:
            return

        header: TARPBroadcastHeader = payload.header
        current_time = self.host.context.scheduler.now()

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
                etx=tarp_utils._etx_est_rssi(
                    rssi, TARPParameters.RSSI_HIGH_REF, TARPParameters.RSSI_LOW_THR
                ),
                num_tx=0,
                num_ack=0,
                adv_metric=header.metric_q124,
            )
            self.nbr_tbl[tx_addr] = tx_entry

        if not self.sink and header.epoch > self.seqn:
            self._reset_connection_status(header.epoch)

        new_metric = tarp_utils._metric(header.metric_q124, tx_entry.etx)
        is_preferred = tarp_utils._preferred(
            new_metric, self.metric, TARPParameters.THR_H, TARPParameters.DELTA_ETX_MIN
        )

        if is_preferred:
            # Unset old parent if it exists
            if self.parent and self.parent in self.nbr_tbl:
                self.nbr_tbl[self.parent].type = self.NodeType.NODE_NEIGHBOR

            self.parent = tx_addr
            self.metric = new_metric
            self.hops = header.hops + 1
            tx_entry.type = self.NodeType.NODE_PARENT
            print(
                f"[{current_time:.6f}s] [{self.host.id}] [TARP] "
                f"SELECTING NEW PARENT {tx_addr.hex()} | New Metric: {self.metric:.2f}",
                flush=True,
            )

            # Schedule beacon forwarding with jitter
            if self._beacon_timer and not self._beacon_timer._cancelled:
                self.host.context.scheduler.unschedule(self._beacon_timer)
            beacon_forward_time = current_time + self._get_beacon_forward_delay()
            self._beacon_timer = NetBeaconSendEvent(
                time=beacon_forward_time, blame=self, callback=self._beacon_timer_cb
            )
            self.host.context.scheduler.schedule(self._beacon_timer)

            # Schedule the first topology report with jitter
            if self._report_timer and not self._report_timer._cancelled:
                self.host.context.scheduler.unschedule(self._report_timer)
            first_report_time = current_time + self._get_next_report_interval()
            self._report_timer = NetTopologyReportSendEvent(
                time=first_report_time, blame=self, callback=self._subtree_report_cb
            )
            self.host.context.scheduler.schedule(self._report_timer)
        else:
            if header.parent == self.host.linkaddr:
                if tx_entry.type != self.NodeType.NODE_CHILD:
                    tx_entry.type = self.NodeType.NODE_CHILD
                    self.tpl_buf[tx_addr] = self.RouteStatus.STATUS_ADD
            elif tx_entry.type == self.NodeType.NODE_CHILD:
                tx_entry.type = self.NodeType.NODE_NEIGHBOR
                if tx_addr in self.tpl_buf:
                    self.tpl_buf.pop(tx_addr)

    def _uc_recv(self, payload: TARPPacket, tx_addr: bytes):
        """Handles a received unicast (data or report) packet."""
        if tx_addr not in self.nbr_tbl:
            return

        header: TARPUnicastHeader = payload.header
        header.hops += 1

        if header.hops > TARPParameters.MAX_PATH_LENGTH:
            return

        self._nbr_tbl_refresh(tx_addr)

        if header.type == TARPUnicastType.UC_TYPE_DATA:
            if header.d_addr == self.host.linkaddr:
                # Packet is for this node - emit receive signal
                signal = TARPReceiveSignal(
                    descriptor="TARPReceive",
                    timestamp=self.host.context.scheduler.now(),
                    received_from=tx_addr,
                    original_source=header.s_addr,
                    packet_type="DATA",
                )
                self._notify_monitors(signal)

                self.host.app.receive(payload.APDU, sender_addr=header.s_addr)
            else:
                # Need to forward the packet - emit forwarding signal
                nexthop = self._nbr_tbl_lookup(header.d_addr)
                if nexthop is not None:
                    signal = TARPForwardingSignal(
                        descriptor="TARPForward",
                        timestamp=self.host.context.scheduler.now(),
                        received_from=tx_addr,
                        original_source=header.s_addr,
                        destination=header.d_addr,
                        forwarding_to=nexthop,
                        packet_type="DATA",
                    )
                    self._notify_monitors(signal)

                self._forward_data(header, payload=payload.APDU)

        elif header.type == TARPUnicastType.UC_TYPE_REPORT:
            net_buf = payload.APDU
            print(
                f"[{self.host.context.scheduler.now():.6f}s] [{self.host.id}] [TARP/REPORT_RECV] "
                f"Received report from {''.join([f'{b:02x}' for b in tx_addr])} with content: {net_buf}",
                flush=True,
            )

            self._nbr_tbl_update(tx_addr=tx_addr, buf=net_buf)

            # if not self.sink:
            #    # Aggregate received info into our own report buffer
            #    self.tpl_buf.update(net_buf)
            #    print(f"[{self.host.context.scheduler.now():.6f}s] [{self.host.id}] [TARP/REPORT_RECV] "
            #    f"Updated tpl_buf: {self.tpl_buf}", flush=True)

    def _uc_sent(self, rx_addr: bytes, status_ok: bool, num_tx: int, ack_rssi: float):
        """Callback from MAC layer indicating unicast transmission outcome."""
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
                alpha=TARPParameters.ALPHA,
                rssi_high_ref=TARPParameters.RSSI_HIGH_REF,
                rssi_low_thr=TARPParameters.RSSI_LOW_THR,
            )
            self._nbr_tbl_refresh(rx_addr)
        else:
            route.age = TARPParameters.ALWAYS_INVALID_AGE
            self._do_cleanup()

    # --- Timer Callbacks ---

    def _beacon_timer_cb(self):
        """Callback to send a beacon."""
        if self.sink:
            new_seqn = self.seqn + 1
            self._reset_connection_status(new_seqn)
            # Schedule next periodic beacon
            next_beacon_time = (
                self.host.context.scheduler.now() + TARPParameters.TREE_BEACON_INTERVAL
            )
            self._beacon_timer = NetBeaconSendEvent(
                time=next_beacon_time, blame=self, callback=self._beacon_timer_cb
            )
            self.host.context.scheduler.schedule(self._beacon_timer)

        broadcast_header = TARPBroadcastHeader(
            epoch=self.seqn, metric_q124=self.metric, hops=self.hops, parent=self.parent
        )
        self._broadcast_send(broadcast_header)

    def _subtree_report_cb(self):
        """Callback to prepare and send a topology report."""
        # This function is now stateful over multiple events for fragmentation
        if self.tpl_buf_offset == 0:
            # First fragment, so build the complete buffer
            self._buff_subtree()

        if self.parent is None:
            self._schedule_next_report()
            return

        if not self.tpl_buf:
            # Send an empty report as a keep-alive
            print(
                f"[{self.host.context.scheduler.now():.6f}s] [{self.host.id}] [TARP/REPORT_SEND] "
                f"Sending empty report to parent {self.parent.hex()}",
                flush=True,
            )
            self._send_report_fragment({})
        else:
            remaining_items = len(self.tpl_buf) - self.tpl_buf_offset
            if remaining_items > 0:
                frag_size = min(remaining_items, TARPParameters.MAX_STAT_PER_FRAGMENT)
                voice_addr = list(self.tpl_buf.keys())
                fragment_payload = {
                    ''.join([f'{b:02x}' for b in addr]) : self.tpl_buf[addr]
                    for addr in voice_addr[
                        self.tpl_buf_offset : self.tpl_buf_offset + frag_size
                    ]
                }
                print(
                    f"[{self.host.context.scheduler.now():.6f}s] [{self.host.id}] [TARP/REPORT_SEND] "
                    f"Sending fragment to parent {self.parent.hex()} with payload: {fragment_payload}",
                    flush=True,
                )
                self._send_report_fragment(fragment_payload)
                self.tpl_buf_offset += frag_size

                # If more fragments remain, schedule next part immediately
                if self.tpl_buf_offset < len(self.tpl_buf):
                    next_frag_time = self.host.context.scheduler.now() + 0.02
                    self._report_timer = NetTopologyReportSendEvent(
                        time=next_frag_time,
                        blame=self,
                        callback=self._subtree_report_cb,
                    )
                    self.host.context.scheduler.schedule(self._report_timer)
                    return  # Exit to avoid scheduling the next periodic report yet

        # All fragments sent (or buffer was empty), schedule next periodic report
        self._flush_tpl_buf()
        self._schedule_next_report()

    def _nbr_tbl_cleanup_cb(self):
        """Callback to periodically clean up expired neighbor entries."""
        self._do_cleanup()
        self._reschedule_cleanup()

    # --- Routing Table and Report Management ---

    def _send_report_fragment(self, payload: Dict[bytes, RouteStatus]):
        """Helper to construct and send a report fragment."""
        if self.parent is None:
            return
        header = TARPUnicastHeader(
            type=TARPUnicastType.UC_TYPE_REPORT,
            s_addr=self.host.linkaddr,
            d_addr=self.parent,
            hops=0,
        )
        packet = TARPPacket(header=header, APDU=payload)
        self.host.mac.send(packet, self.parent)

    def _schedule_next_report(self):
        """Schedules the next periodic topology report."""
        if self.sink or self.parent is None:
            return

        if self._report_timer and not self._report_timer._cancelled:
            self.host.context.scheduler.unschedule(self._report_timer)

        interval = self._get_next_report_interval()
        next_report_time = self.host.context.scheduler.now() + interval
        self._report_timer = NetTopologyReportSendEvent(
            time=next_report_time, blame=self, callback=self._subtree_report_cb
        )
        self.host.context.scheduler.schedule(self._report_timer)

    def _buff_subtree(self):
        """Builds the topology buffer from the current neighbor table."""
        self._flush_tpl_buf()
        for addr, entry in self.nbr_tbl.items():
            if (
                entry.type == self.NodeType.NODE_CHILD
                or entry.type == self.NodeType.NODE_DESCENTANT
            ):
                self.tpl_buf[addr] = self.RouteStatus.STATUS_ADD

    def _change_parent(self, old_parent_addr: bytes):
        """Handles reactive parent change upon link failure."""
        best_metric = float("inf")
        new_parent_addr = None

        # Find the best alternative parent among current neighbors
        for addr, entry in self.nbr_tbl.items():
            if (
                tarp_utils._valid(
                    self.host.context.scheduler.now(),
                    entry,
                    TARPParameters.ENTRY_EXPIRATION_TIME,
                )
                and entry.type == self.NodeType.NODE_NEIGHBOR
            ):
                metric = tarp_utils._metric(entry.adv_metric, entry.etx)
                if metric < best_metric:
                    best_metric = metric
                    new_parent_addr = addr

        # Invalidate the old parent entry
        if old_parent_addr in self.nbr_tbl:
            self.nbr_tbl[old_parent_addr].age = TARPParameters.ALWAYS_INVALID_AGE

        if new_parent_addr:
            self.parent = new_parent_addr
            self.metric = best_metric
            self.nbr_tbl[new_parent_addr].type = self.NodeType.NODE_PARENT
            self.hops = self.nbr_tbl[new_parent_addr].hops + 1

            # Immediately send a report to the new parent
            self._subtree_report_cb()
        else:
            self.parent = None
            self.metric = float("inf")
            self.hops = TARPParameters.MAX_PATH_LENGTH + 1

        print(
            f"[{self.host.context.scheduler.now():.6f}s] [{self.host.id}] [TARP] "
            f"REACTIVELY CHANGING PARENT. Old: {old_parent_addr.hex()}, New: {new_parent_addr.hex() if new_parent_addr else 'None'}.",
            flush=True,
        )

    def _broadcast_send(self, header: TARPBroadcastHeader):
        """Sends a broadcast packet."""
        broadcast_packet = TARPPacket(header=header, APDU=None)
        b_addr = Frame_802_15_4.broadcast_linkaddr
        self.host.mac.send(payload=broadcast_packet, destination=b_addr)

    def _nbr_tbl_lookup(self, dst_addr: bytes) -> Optional[bytes]:
        """Looks up the next hop for a given destination address."""
        if dst_addr == self.host.linkaddr:
            return self.host.linkaddr

        # If destination is in the table, use its specific nexthop
        if dst_addr in self.nbr_tbl:
            route = self.nbr_tbl[dst_addr]
            # Ensure the route is valid before using it
            if tarp_utils._valid(
                self.host.context.scheduler.now(),
                route,
                TARPParameters.ENTRY_EXPIRATION_TIME,
            ):
                return route.nexthop

        # Default route is via parent for any unknown/descendant address
        return self.parent

    def _nbr_tbl_refresh(self, addr: bytes):
        """Refreshes the age of a neighbor table entry."""
        if addr in self.nbr_tbl:
            self.nbr_tbl[addr].age = self.host.context.scheduler.now()

    def _nbr_tbl_update(
        self, tx_addr: bytes, buf: Dict[bytes, "TARPProtocol.RouteStatus"]
    ):
        """Updates the neighbor table based on a received report."""
        # The sender of the report is confirmed as a child
        tx_entry = self.nbr_tbl.get(tx_addr)
        if tx_entry and tx_entry.type == self.NodeType.NODE_NEIGHBOR:
            tx_entry.type = self.NodeType.NODE_CHILD

        for d_addr, d_status in buf.items():
            if d_status == self.RouteStatus.STATUS_ADD:
                if d_addr not in self.nbr_tbl:  # Add new entry
                    d_entry = self.TARPRoute(
                        type=self.NodeType.NODE_DESCENTANT,
                        adv_metric=float("inf"),
                        age=TARPParameters.ALWAYS_VALID_AGE,  # Descendants don't expire
                        hops=TARPParameters.MAX_PATH_LENGTH + 1,
                        nexthop=tx_addr,
                        etx=0.0,
                        num_tx=0,
                        num_ack=0,
                    )
                    self.nbr_tbl[d_addr] = d_entry
                else:  # Refresh existing entry
                    self.nbr_tbl[d_addr].nexthop = tx_addr
                    self.nbr_tbl[d_addr].type = self.NodeType.NODE_DESCENTANT
                    self.nbr_tbl[d_addr].age = TARPParameters.ALWAYS_VALID_AGE

            elif d_status == self.RouteStatus.STATUS_REMOVE:
                if d_addr in self.nbr_tbl:
                    self.nbr_tbl.pop(d_addr)

    def _do_cleanup(self):
        """Performs cleanup of expired neighbor table entries."""
        current_time = self.host.context.scheduler.now()

        expired_addr = [
            addr
            for addr, route in self.nbr_tbl.items()
            if not tarp_utils._valid(
                current_time, route, TARPParameters.ENTRY_EXPIRATION_TIME
            )
        ]

        parent_lost = False
        for addr in expired_addr:
            if addr not in self.nbr_tbl:
                continue

            route_type = self.nbr_tbl[addr].type

            if route_type == self.NodeType.NODE_CHILD:
                self._remove_subtree(addr)
            elif route_type == self.NodeType.NODE_PARENT:
                parent_lost = True

            self.nbr_tbl.pop(addr)

        if parent_lost:
            self._change_parent(old_parent_addr=self.parent)

    def _reschedule_cleanup(self):
        """Reschedules the periodic cleanup timer."""
        if self._cleanup_timer and not self._cleanup_timer._cancelled:
            self.host.context.scheduler.unschedule(self._cleanup_timer)

        cleanup_time = (
            self.host.context.scheduler.now() + TARPParameters.CLEANUP_INTERVAL
        )
        self._cleanup_timer = NetRoutingTableCleanupEvent(
            time=cleanup_time,
            blame=self,
            descriptor=f"Node:{self.host.id}",
            callback=self._nbr_tbl_cleanup_cb,
        )
        self.host.context.scheduler.schedule(self._cleanup_timer)

    def _remove_subtree(self, child_addr: bytes):
        """Removes all descendants routed through a lost child."""
        subtree_addr = [
            addr for addr, route in self.nbr_tbl.items() if route.nexthop == child_addr
        ]
        for addr in subtree_addr:
            if addr in self.nbr_tbl:
                self.nbr_tbl.pop(addr)

        # Announce the removal of the entire subtree in the next report
        self.tpl_buf.update(
            {c_addr: self.RouteStatus.STATUS_REMOVE for c_addr in subtree_addr}
        )
        if child_addr not in self.tpl_buf:
            self.tpl_buf[child_addr] = self.RouteStatus.STATUS_REMOVE
