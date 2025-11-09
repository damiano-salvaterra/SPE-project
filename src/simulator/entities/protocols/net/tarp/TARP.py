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
from simulator.entities.protocols.net.common.tarp_signals import (
    TARPForwardingSignal,
    TARPUnicastReceiveSignal,
    TARPDropSignal,
    TARPBroadcastSendSignal,
    TARPBroadcastReceiveSignal,
    TARPUnicastSendSignal,
    TARPParentChangeSignal,
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
        base_delay = TARPParameters.TREE_BEACON_FORWARD_BASE_DELAY
        jitter = self.rng.uniform(low=0, high=TARPParameters.TREE_BEACON_FORWARD_MAX_JITTER)
        return base_delay + jitter

    def _get_next_report_interval(self) -> float:
        """
        Calculates the interval for the next topology report,
        replicating: SUBTREE_REPORT_INTERVAL * (1 + 1/hops) + random_jitter
        """
        if self.hops <= 0:  # Should only happen for the sink, which doesn't report
            return TARPParameters.SUBTREE_REPORT_OFFEST

        base_interval = TARPParameters.SUBTREE_REPORT_OFFEST * (1.0 + (1.0 / self.hops))

        # Random jitter
        jitter = self.rng.uniform(low=0, high=TARPParameters.SUBTREE_REPORT_MAX_JITTER)

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

    def send(self, payload: Any, destination: Optional[bytes] = None) -> bool:
        """Sends an application data packet to a destination."""
        dest_bytes = destination if destination else b""
        pkt_type_name = TARPUnicastType.UC_TYPE_DATA.name

        if not self.sink and self.parent is None:
            signal = TARPDropSignal(
                descriptor=f"TARP send: No parent, dropping packet (dest: {dest_bytes.hex()}).",
                timestamp=self.host.context.scheduler.now(),
                packet_type=pkt_type_name,
                original_source=self.host.linkaddr,
                final_dest=dest_bytes,
                reason="No Parent",
            )
            self._notify_monitors(signal)
            return False

        nexthop = self._nbr_tbl_lookup(destination)
        if nexthop is None:
            signal = TARPDropSignal(
                descriptor=f"TARP send: No route for destination, dropping packet (dest: {dest_bytes.hex()}).",
                timestamp=self.host.context.scheduler.now(),
                packet_type=pkt_type_name,
                original_source=self.host.linkaddr,
                final_dest=dest_bytes,
                reason="No Route",
            )
            self._notify_monitors(signal)
            return False

        packet_header = TARPUnicastHeader(
            type=TARPUnicastType.UC_TYPE_DATA,
            s_addr=self.host.linkaddr,
            d_addr=destination,
            hops=0,
        )
        net_packet = TARPPacket(header=packet_header, APDU=payload)

        # --- REFACTORED SIGNAL ---
        signal = TARPUnicastSendSignal(
            descriptor=f"TARP send: Sending packet to nexthop {nexthop.hex()} (dest: {dest_bytes.hex()}).",
            timestamp=self.host.context.scheduler.now(),
            packet_type=pkt_type_name,
            original_source=self.host.linkaddr,
            final_dest=dest_bytes,
            tx_hop=self.host.linkaddr,
            rx_hop=nexthop,
        )
        self._notify_monitors(signal)

        self.host.mac.send(payload=net_packet, destination=nexthop)
        return True  # Return True as we found a route and sent to MAC

    def _forward_data(self, header: TARPUnicastHeader, payload: Any, prev_hop: bytes):
        """Forwards a data packet towards its destination."""
        nexthop = self._nbr_tbl_lookup(header.d_addr)
        pkt_type_name = header.type.name

        if nexthop is None:
            signal = TARPDropSignal(
                descriptor=f"TARP forward: No route for destination, dropping packet (dest: {header.d_addr.hex()}).",
                timestamp=self.host.context.scheduler.now(),
                packet_type=pkt_type_name,
                original_source=header.s_addr,
                final_dest=header.d_addr,
                reason="No Route",
            )
            self._notify_monitors(signal)
            return

        net_packet = TARPPacket(header=header, APDU=payload)

        # --- REFACTORED SIGNAL ---
        signal = TARPForwardingSignal(
            descriptor=f"TARP forward: Forwarding packet to nexthop {nexthop.hex()} (source: {header.s_addr.hex()}, dest: {header.d_addr.hex()}).",
            timestamp=self.host.context.scheduler.now(),
            packet_type=pkt_type_name,
            original_source=header.s_addr,
            final_dest=header.d_addr,
            prev_hop=prev_hop,
            tx_hop=self.host.linkaddr,
            rx_hop=nexthop,
        )
        self._notify_monitors(signal)
        self.host.mac.send(payload=net_packet, destination=nexthop)

    def receive(self, payload: TARPPacket, sender_addr: bytes, rssi: float):
        """Handles incoming packets from the MAC layer."""
        if isinstance(payload.header, TARPUnicastHeader):
            self._uc_recv(payload, sender_addr, rssi=rssi)
        elif isinstance(payload.header, TARPBroadcastHeader):
            self._bc_recv(payload, sender_addr, rssi=rssi)

    '''
    def _bc_recv(self, payload: TARPPacket, tx_addr: bytes, rssi: float):
        """Handles a received broadcast (beacon) packet."""

        # if the rssi is too low, ignore the beacon
        if rssi < TARPParameters.RSSI_LOW_THR:
            return

        header: TARPBroadcastHeader = payload.header

        # if the beacon is from an old epoch, ignore it
        if not self.sink and header.epoch < self.seqn:
            return

        signal = TARPBroadcastReceiveSignal(
            descriptor=f"TARP beacon receive: broadcast received from {tx_addr.hex()} with seqn {header.epoch} and adv_metric {header.metric_q124}",
            timestamp=self.host.context.scheduler.now(),
            source=tx_addr,
            rssi=rssi,
        )
        self._notify_monitors(signal)

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

        is_from_current_parent = self.parent is not None and self.parent == tx_addr

        new_metric = tarp_utils._metric(header.metric_q124, tx_entry.etx)

        if is_from_current_parent:  # if from current parent, is just a refresh
            self.metric = new_metric
            self.hops = header.hops + 1
            if header.epoch > self.seqn: #if it is a new epcoh, I update the counter and forward the beacon
                self.seqn = header.epoch

                if (
                    self._beacon_timer and not self._beacon_timer._cancelled
                ):  # if there is an acrtive beacon timer(scheduled event), cancel it
                    self.host.context.scheduler.unschedule(self._beacon_timer)
                beacon_forward_time = (
                    current_time + self._get_beacon_forward_delay()
                )  # reschedule
                self._beacon_timer = NetBeaconSendEvent(
                    time=beacon_forward_time, blame=self, callback=self._beacon_timer_cb
                )
                self.host.context.scheduler.schedule(self._beacon_timer)

            #if is not a new epoch, I dont forward the beaocon again, to avoid broadcast storms
            return  # no need to do anything else

        # if the beacon is from a different node, check if it is preferred
        is_preferred = tarp_utils._preferred(
            new_metric, self.metric, TARPParameters.THR_H, TARPParameters.DELTA_ETX_MIN
        )
        if is_preferred:
            # Unset old parent if it exists
            old_parent = None

            if (
                not self.sink and header.epoch > self.seqn
            ):  # if it is a new epoch, reset connection status
                self._reset_connection_status(header.epoch) #FIXME: this is inconsistent: it deletes the subtree, but only if it finds a bette rparent

            if self.parent and self.parent in self.nbr_tbl:
                self.nbr_tbl[self.parent].type = self.NodeType.NODE_NEIGHBOR
                old_parent = self.parent

            self.parent = tx_addr
            self.metric = new_metric
            self.hops = header.hops + 1
            tx_entry.type = self.NodeType.NODE_PARENT
            self.seqn = header.epoch

            signal = TARPParentChangeSignal(
                descriptor=f"TARP parent change: changing parent from {(old_parent if old_parent else b'').hex()} to {self.parent.hex()}.",
                timestamp=current_time,
                old_parent=old_parent if old_parent else b"",
                new_parent=self.parent,
            )
            self._notify_monitors(signal)

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

        else:  # if not preferred, just update type
            if header.parent == self.host.linkaddr:
                if tx_entry.type != self.NodeType.NODE_CHILD:
                    tx_entry.type = self.NodeType.NODE_CHILD
                    self.tpl_buf[tx_addr] = self.RouteStatus.STATUS_ADD
            elif tx_entry.type == self.NodeType.NODE_CHILD:
                tx_entry.type = self.NodeType.NODE_NEIGHBOR
                if tx_addr in self.tpl_buf:
                    self.tpl_buf.pop(tx_addr)
    '''

    def _bc_recv(self, payload: TARPPacket, tx_addr: bytes, rssi: float):
        """Handles a received broadcast (beacon) packet."""

        # --- PRELIMINARY CHECKS ---

        # if the rssi is too low, ignore the beacon
        if rssi < TARPParameters.RSSI_LOW_THR:
            return

        header: TARPBroadcastHeader = payload.header
        current_time = self.host.context.scheduler.now()

        # if the beacon is from an old epoch, ignore it
        # (The sink generates epochs, it doesn't learn them)
        if not self.sink and header.epoch < self.seqn:
            return

        # --- CRITICAL FIX: NEW EPOCH HANDLING ---

        # If this beacon is from a new epoch, the node MUST reset its state
        # REGARDLESS of who sent it. This is the core logic fix.
        # This solves the bug where re-hearing from the *same parent* in a new
        # epoch did not trigger a reset.
        if not self.sink and header.epoch > self.seqn:
            # You must choose Strategy 1 OR 2 for this function call.
            self._reset_connection_status(header.epoch)
            # Note: _reset_connection_status() also updates self.seqn

        # This handles the case where a node is just starting up (seqn=0)
        # and needs to adopt the current network epoch.
        elif self.seqn == 0 and not self.sink:
            self.seqn = header.epoch

        # --- END OF CRITICAL FIX ---

        signal = TARPBroadcastReceiveSignal(
            descriptor=f"TARP beacon receive: broadcast received from {tx_addr.hex()} with seqn {header.epoch} and adv_metric {header.metric_q124}",
            timestamp=current_time,
            source=tx_addr,
            rssi=rssi,
        )
        self._notify_monitors(signal)

        # --- NEIGHBOR TABLE MANAGEMENT ---

        # Now that the epoch is consistent, update or create the neighbor entry
        tx_entry = self.nbr_tbl.get(tx_addr)

        if tx_entry:
            self._nbr_tbl_refresh(addr=tx_addr)
            tx_entry.adv_metric = header.metric_q124
            # We must also update these fields in case the entry already existed
            tx_entry.hops = header.hops
            tx_entry.etx = tarp_utils._etx_est_rssi(
                rssi, TARPParameters.RSSI_HIGH_REF, TARPParameters.RSSI_LOW_THR
            )
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

        # --- PARENT SELECTION LOGIC ---

        # 'is_from_current_parent' will now ALWAYS be FALSE at the start of a
        # new epoch, because _reset_connection_status() sets self.parent = None.
        # This forces all nodes to re-evaluate their parent choice.
        is_from_current_parent = self.parent is not None and self.parent == tx_addr
        new_metric = tarp_utils._metric(header.metric_q124, tx_entry.etx)

        if is_from_current_parent:
            # This block now only runs for SAME-EPOCH refreshes.
            self.metric = new_metric
            self.hops = header.hops + 1
            # Do not forward refresh beacons to avoid broadcast storms
            return

        # Check if this sender is a preferred parent
        is_preferred = tarp_utils._preferred(
            new_metric, self.metric, TARPParameters.THR_H, TARPParameters.DELTA_ETX_MIN
        )

        if is_preferred:
            old_parent = self.parent
            # Demote old parent (if any) to a regular neighbor
            if old_parent and old_parent in self.nbr_tbl:
                self.nbr_tbl[old_parent].type = self.NodeType.NODE_NEIGHBOR

            # Set new parent
            self.parent = tx_addr
            self.metric = new_metric
            self.hops = header.hops + 1
            tx_entry.type = self.NodeType.NODE_PARENT

            # This update is technically redundant if a reset just happened,
            # but it's crucial for the case where a node was orphaned
            # (self.parent = None) and finds a parent in the *same* epoch.
            self.seqn = header.epoch

            signal = TARPParentChangeSignal(
                descriptor=f"TARP parent change: changing parent from {(old_parent if old_parent else b'').hex()} to {self.parent.hex()}. New metric {self.metric}.",
                timestamp=current_time,
                old_parent=old_parent if old_parent else b"",
                new_parent=self.parent,
            )
            self._notify_monitors(signal)

            # Schedule beacon forwarding with jitter
            if self._beacon_timer and not self._beacon_timer._cancelled:
                self.host.context.scheduler.unschedule(self._beacon_timer)
            beacon_forward_time = current_time + self._get_beacon_forward_delay()
            self._beacon_timer = NetBeaconSendEvent(
                time=beacon_forward_time, blame=self, callback=self._beacon_timer_cb
            )
            self.host.context.scheduler.schedule(self._beacon_timer)

            '''
            # Schedule the first topology report with jitter
            # This is now correctly scheduled even if the parent is the same
            # as the previous epoch, because the reset forced re-selection.
            if self._report_timer and not self._report_timer._cancelled:
                self.host.context.scheduler.unschedule(self._report_timer)
            first_report_time = current_time + self._get_next_report_interval()
            self._report_timer = NetTopologyReportSendEvent(
                time=first_report_time, blame=self, callback=self._subtree_report_cb
            )
            self.host.context.scheduler.schedule(self._report_timer)
            '''

            # Schedule the first topology report immediately with jitter
            # This is critical for fast network convergence after an epoch change.
            # The periodic report will be scheduled by _subtree_report_cb itself.
            if self._report_timer and not self._report_timer._cancelled:
                self.host.context.scheduler.unschedule(self._report_timer)
            
            
            if self.hops > 0:
                base_delay = TARPParameters.INITIAL_REPORT_BASE_DELAY / self.hops
            else:
                base_delay = 0.0 # Should not happen for non-sink, but safe guard

            jitter = self.rng.uniform(low=0, high=TARPParameters.INITIAL_REPORT_MAX_JITTER)
            immediate_report_time = current_time + base_delay + jitter

            self._report_timer = NetTopologyReportSendEvent(
                time=immediate_report_time, blame=self, callback=self._subtree_report_cb
            )
            self.host.context.scheduler.schedule(self._report_timer)

            
        else:  # Not preferred, just check if it's a child
            if header.parent == self.host.linkaddr:
                if tx_entry.type != self.NodeType.NODE_CHILD:
                    tx_entry.type = self.NodeType.NODE_CHILD
                    self.tpl_buf[tx_addr] = self.RouteStatus.STATUS_ADD
            elif tx_entry.type == self.NodeType.NODE_CHILD:
                # The node was our child, but is no longer.
                tx_entry.type = self.NodeType.NODE_NEIGHBOR
                if tx_addr in self.tpl_buf:
                    # Remove from pending report
                    self.tpl_buf.pop(tx_addr)

    def _uc_recv(self, payload: TARPPacket, tx_addr: bytes, rssi: float):
        """Handles a received unicast (data or report) packet."""

        tx_entry = self.nbr_tbl.get(tx_addr)
        current_time = self.host.context.scheduler.now()
        header: TARPUnicastHeader = payload.header
        pkt_type_name = header.type.name

        if tx_entry is None:
            # NOTE!!!!! VERY IMPORTANT: This is a fundamental flaw of the protocol, discovered during simulations:
            # in the case the received packet is from a node that is selecting me as a parent during tree formation, if i did not
            # receive a beacon from it before, it will not be in my nbr_tbl, and I will drop its packets, making tree formation impossible
            # NOTE: we will add a reactive insertion of the sender into nbr_tbl as a child with unknown metric to allow the treeformation.
            # If the packet is a data apcket, i can still safely drop it

            if (
                header.type == TARPUnicastType.UC_TYPE_REPORT
            ):  # if this is a report, we can assume this is a child that selected me as parent
                # I can reactively add it to nbr_tbl
                initial_etx = tarp_utils._etx_est_rssi(
                    rssi, TARPParameters.RSSI_HIGH_REF, TARPParameters.RSSI_LOW_THR
                )
                tx_entry = self.TARPRoute(
                    type=self.NodeType.NODE_CHILD,
                    age=current_time,
                    nexthop=tx_addr,
                    hops=header.hops + 1,
                    etx=initial_etx,
                    num_tx=0,
                    num_ack=0,
                    adv_metric=float("inf"),
                )
                self.nbr_tbl[tx_addr] = tx_entry

            #else:  # If it is a data packet from unknown sender, drop it
            #    signal = TARPDropSignal(
            #        descriptor=f"TARP unicast receive: dropping {pkt_type_name} from unknown sender {tx_addr.hex()}.",
            #        timestamp=current_time,
            #        packet_type=pkt_type_name,
            #        original_source=header.s_addr,
            #        final_dest=header.d_addr,
            #        reason="Unknown Sender",
            #    )
            #    self._notify_monitors(signal)
            #    return

        header.hops += 1
        if tx_entry is not None:
            self._nbr_tbl_refresh(tx_addr)

        if header.hops > TARPParameters.MAX_PATH_LENGTH:
            # Max hops exceeded, drop.
            signal = TARPDropSignal(
                descriptor=f"TARP drop: packet exceeded max hops (hops: {header.hops}).",
                timestamp=current_time,
                packet_type=pkt_type_name,
                original_source=header.s_addr,
                final_dest=header.d_addr,
                reason="Max Hops",
            )
            self._notify_monitors(signal)
            return


        report_content_str = None  # Will be set only for reports

        if header.type == TARPUnicastType.UC_TYPE_DATA:
            if header.d_addr == self.host.linkaddr:
                # This is the final destination
                # --- REFACTORED SIGNAL (RECEIVE) ---
                signal = TARPUnicastReceiveSignal(
                    descriptor=f"TARP unicast receive: DATA received from {tx_addr.hex()} (orig: {header.s_addr.hex()}).",
                    timestamp=current_time,
                    packet_type=pkt_type_name,
                    original_source=header.s_addr,
                    final_dest=header.d_addr,
                    tx_hop=tx_addr,
                    rx_hop=self.host.linkaddr,
                )
                self._notify_monitors(signal)
                self.host.app.receive(
                    payload.APDU, sender_addr=header.s_addr, hops=header.hops
                )
            else:
                # Not for me, forward it
                # --- REFACTORED SIGNAL (FORWARD) ---
                self._forward_data(header, payload=payload.APDU, prev_hop=tx_addr)

        elif header.type == TARPUnicastType.UC_TYPE_REPORT:
            net_buf = payload.APDU

            # Prepare report content for logging
            net_buf_str = {addr.hex(): status.name for addr, status in net_buf.items()}
            report_content_str = str(net_buf_str)  # Store for signal

            # --- REFACTORED SIGNAL (RECEIVE) ---
            signal = TARPUnicastReceiveSignal(
                descriptor=f"TARP report receive: report received from {tx_addr.hex()} with content: {report_content_str}.",
                timestamp=current_time,
                packet_type=pkt_type_name,
                original_source=header.s_addr,
                final_dest=header.d_addr,
                tx_hop=tx_addr,
                rx_hop=self.host.linkaddr,
                report_content=report_content_str,
            )
            self._notify_monitors(signal)

            self._nbr_tbl_update(tx_addr=tx_addr, buf=net_buf)

            if not self.sink:
                # Aggregate received info into our own report buffer
                self.tpl_buf.update(net_buf)

                #unschedule periodic report and send a reactive report
                if self._report_timer and not self._report_timer._cancelled:
                    self.host.context.scheduler.unschedule(self._report_timer)

                jitter = self.rng.uniform(low=0.0, high=TARPParameters.SUBTREE_REPORT_MAX_JITTER) # 0-0.1s jitter  
                delay = TARPParameters.SUBTREE_REPORT_DELAY + jitter
                
                self._report_timer = NetTopologyReportSendEvent(
                    time=self.host.context.scheduler.now() + delay,
                    blame=self,
                    callback=self._subtree_report_cb,
                )
                self.host.context.scheduler.schedule(self._report_timer)

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

        if status_ok:            
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
        if self.tpl_buf_offset == 0 and not self.tpl_buf: #if the buffer is empy (periodic report and not reactive)
            # First fragment, so build the complete buffer
            self._buff_subtree()

        if self.parent is None: 
            self._schedule_next_report()
            return

        if not self.tpl_buf:
            # Send an empty report as a keep-alive
            self._send_report_fragment({})
        else:
            remaining_items = len(self.tpl_buf) - self.tpl_buf_offset
            if remaining_items > 0:
                frag_size = min(remaining_items, TARPParameters.MAX_STAT_PER_FRAGMENT)
                voice_addr = list(self.tpl_buf.keys())
                fragment_payload = {
                    addr: self.tpl_buf[addr]
                    for addr in voice_addr[
                        self.tpl_buf_offset : self.tpl_buf_offset + frag_size
                    ]
                }

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

        pkt_type_name = TARPUnicastType.UC_TYPE_REPORT.name
        header = TARPUnicastHeader(
            type=TARPUnicastType.UC_TYPE_REPORT,
            s_addr=self.host.linkaddr,
            d_addr=self.parent,
            hops=0,
        )
        packet = TARPPacket(header=header, APDU=payload)

        # --- REFACTORED SIGNAL ---
        signal = TARPUnicastSendSignal(
            descriptor=f"TARP report send: Sending packet to parent {self.parent.hex()}.",
            timestamp=self.host.context.scheduler.now(),
            packet_type=pkt_type_name,
            original_source=self.host.linkaddr,
            final_dest=self.parent,
            tx_hop=self.host.linkaddr,
            rx_hop=self.parent,
        )
        self._notify_monitors(signal)
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

    '''
    def _change_parent(self, old_parent_addr: bytes):
        """Handles reactive parent change upon link failure."""
        best_metric = float("inf")
        new_parent_addr = None

        # Find the best alternative parent among current neighbors
        for addr, entry in self.nbr_tbl.items():
            #if (
            #    tarp_utils._valid(
            #        self.host.context.scheduler.now(),
            #        entry,
            #        TARPParameters.ENTRY_EXPIRATION_TIME,
            #    )
            #    and entry.type == self.NodeType.NODE_NEIGHBOR
            #): 
            #in the original protocol the validity check is not implemented
            if entry.type == self.NodeType.NODE_NEIGHBOR:
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

        signal = TARPParentChangeSignal(
            descriptor=f"TARP reactive parent change: changing parent from {old_parent_addr.hex()} to {new_parent_addr.hex() if new_parent_addr else 'None'}.",
            timestamp=self.host.context.scheduler.now(),
            old_parent=old_parent_addr,
            new_parent=new_parent_addr if new_parent_addr else b"",
        )
        self._notify_monitors(signal)
    '''
    def _change_parent(self, old_parent_addr: bytes):
        """Handles reactive parent change upon link failure."""
        best_metric = float("inf")
        new_parent_addr = None
        new_parent_hops = TARPParameters.MAX_PATH_LENGTH + 1
        old_parent_entry = self.nbr_tbl.get(old_parent_addr)

        # Find the best alternative parent among current neighbors
        # old parent is still in the table, but marked as NODE_PARENT, so the loop ignores it
        for addr, entry in self.nbr_tbl.items():
            if entry.type == self.NodeType.NODE_NEIGHBOR:
                metric = tarp_utils._metric(entry.adv_metric, entry.etx)
                if metric < best_metric:
                    best_metric = metric
                    new_parent_addr = addr
                    new_parent_hops = entry.hops

        # now we mark the old parent as invalid
        if old_parent_entry is not None:
            old_parent_entry.type = self.NodeType.NODE_NEIGHBOR # downgrade to neighbor
            old_parent_entry.age = TARPParameters.ALWAYS_INVALID_AGE

        if new_parent_addr:
            # Promote new parent
            self.parent = new_parent_addr
            self.metric = best_metric
            self.nbr_tbl[new_parent_addr].type = self.NodeType.NODE_PARENT
            self.hops = new_parent_hops + 1

            # Immediately send a report to the new parent
            self._subtree_report_cb()
        else:
            # No parent found, become orphan and disconnect
            self.parent = None
            self.metric = float("inf")
            self.hops = TARPParameters.MAX_PATH_LENGTH + 1

        signal = TARPParentChangeSignal(
            descriptor=f"TARP reactive parent change: changing parent from {old_parent_addr.hex()} to {new_parent_addr.hex() if new_parent_addr else 'None'}.",
            timestamp=self.host.context.scheduler.now(),
            old_parent=old_parent_addr,
            new_parent=new_parent_addr if new_parent_addr else b"",
        )
        self._notify_monitors(signal)


    def _broadcast_send(self, header: TARPBroadcastHeader):
        """Sends a broadcast packet."""
        broadcast_packet = TARPPacket(header=header, APDU=None)
        b_addr = Frame_802_15_4.broadcast_linkaddr

        signal = TARPBroadcastSendSignal(
            descriptor=f"TARP beacon send: broadcasting beacon: epoch->{header.epoch}, metric->{header.metric_q124}, hops->{header.hops}, parent->{header.parent.hex()  if header.parent else '' }.",
            timestamp=self.host.context.scheduler.now(),
            epoch=header.epoch,
            metric=header.metric_q124,
            hops=header.hops,
        )
        self._notify_monitors(signal)
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
    '''
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

            self.nbr_tbl.pop(addr, None)

        if parent_lost:
            self._change_parent(old_parent_addr=self.parent)
    '''
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
        addrs_to_remove = []

        for addr in expired_addr:
            if addr not in self.nbr_tbl:
                continue
            
            route_type = self.nbr_tbl[addr].type

            if route_type == self.NodeType.NODE_PARENT:
                parent_lost = True  
            elif route_type == self.NodeType.NODE_CHILD:
                self._remove_subtree(addr)
                addrs_to_remove.append(addr)
            else:
                addrs_to_remove.append(addr)

        if parent_lost:
            self._change_parent(old_parent_addr=self.parent)

            if self.parent not in addrs_to_remove:
                 addrs_to_remove.append(self.parent)

        for addr in addrs_to_remove:
            if addr in self.nbr_tbl:
                 if not tarp_utils._valid(current_time, self.nbr_tbl[addr], TARPParameters.ENTRY_EXPIRATION_TIME):
                    self.nbr_tbl.pop(addr, None)

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
