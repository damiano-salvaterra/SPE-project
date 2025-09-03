from simulator.entities.protocols.common.Layer import Layer
from simulator.entities.common.Entity import Entity
from simulator.engine.common.signals import PacketSignal
from simulator.entities.protocols.phy.common.phy_events import (PhyTxEndEvent, PhyTxStartEvent, PhyUnsyncEvent)
from simulator.entities.protocols.phy.common.Transmission import Transmission
from simulator.entities.protocols.common.packets import MACFrame, Frame_802154, Ack_802154
from numpy import log10
from typing import TYPE_CHECKING, Dict

if TYPE_CHECKING:
    from simulator.entities.protocols.phy.common.ReceptionSession import ReceptionSession
    from simulator.entities.physical.devices.nodes import StaticNode
    from simulator.entities.physical.media.WirelessChannel import WirelessChannel

class SimplePhyLayer(Layer, Entity):
    def __init__(self, host: "StaticNode", transmission_power: float = 0):
        Layer.__init__(self, host=host)
        Entity.__init__(self)
        self.capture_threshold_dB = 5
        self.cca_Threshold_dBm = -85
        self.correlator_threshold = -95
        self.transmission_power = transmission_power
        self.transmission_media = None

        # State management for the receiver
        self.active_session: "ReceptionSession" = None
        self.transmitting = False
        self.synchronized_tx: "Transmission" = None
        self.reception_power_state: Dict["Transmission", float] = {}

        # State for MAC/NET layers
        self._last_seqn = 0
        self._last_successful_rx_rssi_dBm: float = -150.0

    def connect_transmission_media(self, transmission_media: "WirelessChannel"):
        self.transmission_media = transmission_media

    def _is_decoded(self, session: "ReceptionSession") -> bool:
        """
        Calculates the SINR for the captured transmission and determines if it can be decoded.
        This method uses the "worst-case SINR" model: the packet is lost if the SINR
        drops below the capture threshold at any point during the reception.
        """
        noise_floor_linear = self.transmission_media.get_linear_noise_floor()
        capturing_tx_power_linear = self.reception_power_state.get(session.capturing_tx, 0.0)
        
        if not session.reception_segments or capturing_tx_power_linear == 0.0:
            return False

        min_sinr = float('inf')
        for segment in session.reception_segments:
            interferers_power = sum(
                self.reception_power_state.get(tx, 0.0) for tx in segment.interferers
            )
            segment_sinr = capturing_tx_power_linear / (noise_floor_linear + interferers_power)
            if segment_sinr < min_sinr:
                min_sinr = segment_sinr

        min_sinr_db = 10 * log10(min_sinr) if min_sinr > 0 else -float('inf')
        return min_sinr_db >= self.capture_threshold_dB

    def on_PhyRxStartEvent(self, transmission: Transmission):
        """
        Handles the start of a signal's arrival at the receiver.
        REVISED LOGIC: Implements a "first-come, first-served" model.
        - If the radio is idle, it attempts to lock onto the new signal.
        - If the radio is already locked onto a signal, any new arrival is treated as interference.
        This removes the unrealistic "mid-packet capture" model.
        """
        # Sample the channel for the new transmission and store its power.
        received_power_linear = self.transmission_media.get_linear_link_budget(
            node1=self.host, node2=transmission.transmitter, tx_power_dBm=transmission.transmission_power_dBm
        )
        self.reception_power_state[transmission] = received_power_linear

        # If the radio is already busy receiving a packet, this new signal is just an interferer.
        if self.active_session:
            self.active_session.notify_tx_start(transmission=transmission)
            return

        # --- The Radio is currently IDLE ---
        # Check if the signal is strong enough to be detected and start a reception.
        received_power_dBm = 10 * log10(received_power_linear * 1000)
        if received_power_dBm < self.correlator_threshold:
            # Signal is too weak to be detected. Clean up its state and remain idle.
            del self.reception_power_state[transmission]
            return

        # The signal is strong enough. Start a new reception session and lock onto it.
        self._open_session(transmission)
        self.synchronized_tx = transmission # This is the packet we are now trying to decode.

        # Schedule events to check if the packet is addressed to us after the address fields are received.
        if isinstance(transmission.packet, Ack_802154):
            is_for_me = (transmission.packet.seqn == self._last_seqn)
            detection_time = self.host.context.scheduler.now() + transmission.packet.ack_detection_time
            if not is_for_me:
                unsync_event = PhyUnsyncEvent(time=detection_time, blame=self, callback=self._unsynchronize)
                self.host.context.scheduler.schedule(unsync_event)
        
        elif isinstance(transmission.packet, Frame_802154):
            is_for_me = (transmission.packet.rx_addr == self.host.linkaddr or
                         transmission.packet.rx_addr == Frame_802154.broadcast_linkaddr)
            detection_time = self.host.context.scheduler.now() + transmission.packet.daddr_detection_time
            if not is_for_me:
                unsync_event = PhyUnsyncEvent(time=detection_time, blame=self, callback=self._unsynchronize)
                self.host.context.scheduler.schedule(unsync_event)

    def _unsynchronize(self):
        """Called when the radio determines the packet is not for it. It will continue receiving
        to assess CCA but will not attempt to decode the frame."""
        self.synchronized_tx = None

    def on_PhyRxEndEvent(self, transmission: Transmission):
        """
        Handles the end of a signal's arrival at the receiver.
        REVISED LOGIC: The radio only makes a decoding decision if the ending transmission
        was the one it was synchronized to.
        """
        # Ignore if there's no active session or if this transmission wasn't being tracked.
        if not self.active_session or transmission not in self.reception_power_state:
            self.reception_power_state.pop(transmission, None) # Cleanup just in case
            return

        is_capturing_tx_ended = (self.active_session.capturing_tx == transmission)

        if is_capturing_tx_ended:
            # The reception attempt is now complete. We must decide its fate.
            is_decoded = self._is_decoded(self.active_session)
            
            # Retrieve packet info before we clean up the session.
            received_packet = self.active_session.capturing_tx.packet
            capturing_tx_power_linear = self.reception_power_state.get(transmission)

            # The reception attempt is over. The radio is now idle.
            self._close_session()

            # Pass the packet up the stack ONLY if it was successfully decoded and for us.
            if is_decoded and self.synchronized_tx:
                rssi_dBm = 10 * log10(capturing_tx_power_linear * 1000)
                self._last_successful_rx_rssi_dBm = rssi_dBm
                self.receive(payload=received_packet)
            # else: The packet was lost to interference/noise or was not for us. Do nothing.
        else:
            # An interfering transmission has ended. This improves the SINR for the rest
            # of our reception. Notify the session and remove the interferer from our state.
            self.active_session.notify_tx_end(transmission=transmission)
            self.reception_power_state.pop(transmission, None)

    def _open_session(self, transmission: Transmission):
        from simulator.entities.protocols.phy.common.ReceptionSession import ReceptionSession
        
        # When a new session opens, any other signals already being received are interferers.
        current_interferers = [
            tx for tx in self.reception_power_state.keys() if tx is not transmission
        ]

        self.active_session = ReceptionSession(
            receiving_node=self.host,
            capturing_tx=transmission,
            interferers=current_interferers,
            start_time=self.host.context.scheduler.now()
        )

    def _close_session(self):
        """
        REVISED: Ends a reception session and fully clears all related receiver state,
        making the radio truly idle.
        """
        if self.active_session:
            self.active_session = None
            self.synchronized_tx = None
            # Crucially, when a reception attempt ends, we no longer track any powers.
            # A new session will re-sample everything from a clean slate.
            self.reception_power_state.clear()
            
    def on_PhyTxStartEvent(self, transmission: Transmission):
        self.transmitting = True
        self.transmission_media.on_PhyTxStartEvent(transmission=transmission)

    def on_PhyTxEndEvent(self, transmission: Transmission):
        self.transmitting = False
        self.transmission_media.on_PhyTxEndEvent(transmission=transmission)
        self.host.rdc.on_PhyTxEndEvent(packet=transmission.packet)
        
    def send(self, payload: MACFrame):
        signal = PacketSignal(
            descriptor="PHY Packet Transmission",
            timestamp=self.host.context.scheduler.now(),
            event_type="PacketSent",
            packet=payload
        )
        self._notify_monitors(signal)

        if isinstance(payload, Frame_802154):
            self._last_seqn = payload.seqn

        transmission = Transmission(transmitter=self.host, packet=payload, transmission_power_dBm=self.transmission_power)
        
        start_tx_time = self.host.context.scheduler.now() + 1e-12
        end_tx_time = start_tx_time + payload.on_air_duration
        tx_start_event = PhyTxStartEvent(time=start_tx_time, blame=self, callback=self.on_PhyTxStartEvent, transmission=transmission)
        tx_end_event = PhyTxEndEvent(time=end_tx_time, blame=self, callback=self.on_PhyTxEndEvent, transmission=transmission)

        self.host.context.scheduler.schedule(tx_start_event)
        self.host.context.scheduler.schedule(tx_end_event)

    def cca_802154_Mode1(self) -> bool:
        if self.is_radio_busy():
            return True
        
        noise_floor = self.transmission_media.get_linear_noise_floor()
        channel_power = 0.0
        # Sample all active transmissions on the channel right now.
        for transmission in self.transmission_media.active_transmissions.values():
            power_contribute = self.transmission_media.get_linear_link_budget(self.host, transmission.transmitter, transmission.transmission_power_dBm)
            channel_power += power_contribute

        total_received_power = channel_power + noise_floor
        total_dBm = 10 * log10(total_received_power * 1000)
        return total_dBm > self.cca_Threshold_dBm

    def is_radio_busy(self) -> bool:
        # The radio is considered busy if it's transmitting OR in the middle of a reception attempt.
        return self.transmitting or (self.active_session is not None)

    def receive(self, payload: MACFrame):
        signal = PacketSignal(
            descriptor="PHY Packet Reception",
            timestamp=self.host.context.scheduler.now(),
            event_type="PacketReceived",
            packet=payload
        )
        self._notify_monitors(signal)

        self.host.rdc.receive(payload=payload)

    def get_last_rssi(self) -> float:
        return self._last_successful_rx_rssi_dBm