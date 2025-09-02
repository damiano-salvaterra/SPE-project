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

        self.last_session: "ReceptionSession" = None
        self.active_session = False
        self.transmitting = False
        self.synchronized_tx: "Transmission" = None
        
        self.reception_power_state: Dict["Transmission", float] = {}

        self._last_seqn = 0
        self._last_successful_rx_rssi_dBm: float = -150.0

    def connect_transmission_media(self, transmission_media: "WirelessChannel"):
        self.transmission_media = transmission_media

    def _is_decoded(self, session: "ReceptionSession"):
        noise_floor_linear = self.transmission_media.get_linear_noise_floor()
        capturing_tx_power_linear = self.reception_power_state.get(session.capturing_tx, 0.0)
        
        if not session.reception_segments or capturing_tx_power_linear == 0.0:
            return False

        segments_SINR = []
        for i, segment in enumerate(session.reception_segments):
            interferers_power = sum(
                self.reception_power_state.get(tx, 0.0) for tx in segment.interferers
            )
            segment_SINR = capturing_tx_power_linear / (noise_floor_linear + interferers_power)
            segments_SINR.append(segment_SINR)

        min_SINR = min(segments_SINR)
        min_SINR_dB = 10 * log10(min_SINR) if min_SINR > 0 else -float('inf')

        result = min_SINR_dB >= self.capture_threshold_dB
        return result


    def on_PhyRxStartEvent(self, transmission: Transmission):
        received_power_linear = self.transmission_media.get_linear_link_budget(
            node1=self.host, node2=transmission.transmitter, tx_power_dBm=transmission.transmission_power_dBm
        )
        received_power_dBm = 10 * log10(received_power_linear * 1000)
        
        self.reception_power_state[transmission] = received_power_linear

        if received_power_dBm < self.correlator_threshold:
            del self.reception_power_state[transmission]
            if not self.reception_power_state and self.active_session:
                self._close_session()
            return

        if not self.active_session:
            # Radio is idle, this transmission starts a new session.
            self._open_session(transmission)
            self.synchronized_tx = transmission
        else:
            # Radio is busy. Check if the new signal can capture the receiver.
            current_capturing_power = self.reception_power_state.get(self.last_session.capturing_tx, 0.0)
            new_signal_power = received_power_linear
            
            # Convert capture threshold from dB to a linear ratio
            capture_ratio = 10**(self.capture_threshold_dB / 10)

            if new_signal_power > current_capturing_power * capture_ratio:
                # CAPTURE! The new signal is significantly stronger.
                # The old packet is now considered lost due to this capture event.
                # Close the old session and start a new one for the new signal.
                self._close_session()
                self._open_session(transmission)
                self.synchronized_tx = transmission
            else:
                # No capture. The new signal is just an interferer for the ongoing session.
                self.last_session.notify_tx_start(transmission=transmission)
        
        # This logic now applies to whichever transmission is currently synchronized
        if self.synchronized_tx == transmission:
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
        """Called when the radio determines the packet is not for it."""
        self.synchronized_tx = None


    def on_PhyRxEndEvent(self, transmission: Transmission):
        if not self.active_session or transmission not in self.reception_power_state:
            self.reception_power_state.pop(transmission, None)
            return

        is_capturing_ended = (self.last_session.capturing_tx == transmission)

        if is_capturing_ended:
            # This is the end of the packet we were trying to receive.
            received_packet = self.last_session.capturing_tx.packet
            is_decoded = self._is_decoded(self.last_session)
            
            ended_tx_power_linear = self.reception_power_state.get(transmission, None)
            
            self.reception_power_state.pop(transmission, None)
            self._close_session() # End the current session immediately.

            if is_decoded and ended_tx_power_linear is not None:
                rssi_dBm = 10 * log10(ended_tx_power_linear * 1000)
                self._last_successful_rx_rssi_dBm = rssi_dBm
                self.receive(payload=received_packet)
            else:
                # Packet was lost, do nothing.
                pass
            
            # --- REMOVED LOGIC ---
            # The original code had a block here to find the "strongest_remaining_tx"
            # and start a new session. This was the source of the unrealistic
            # "late-stage capture" and has been REMOVED. The radio is now idle
            # and will wait for a new PhyRxStartEvent to begin the next reception.

        else: # The ended transmission was an interferer for the active session
            self.reception_power_state.pop(transmission, None)
            if self.last_session:
                 self.last_session.notify_tx_end(transmission=transmission)

    def _open_session(self, transmission: Transmission):
        from simulator.entities.protocols.phy.common.ReceptionSession import ReceptionSession
        
        current_interferers = [
            tx for tx in self.reception_power_state.keys()
            if tx is not transmission
        ]

        self.last_session = ReceptionSession(
            receiving_node=self.host,
            capturing_tx=transmission,
            interferers=current_interferers,
            start_time=self.host.context.scheduler.now()
        )
        self.active_session = True

    def _close_session(self):
        if self.active_session:
            self.active_session = False
            self.synchronized_tx = None
            self.last_session = None

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
        for transmission in self.transmission_media.active_transmissions.values():
            power_contribute = self.transmission_media.get_linear_link_budget(self.host, transmission.transmitter, transmission.transmission_power_dBm)
            channel_power += power_contribute

        total_received_power = channel_power + noise_floor
        total_dBm = 10 * log10(total_received_power * 1000)
        return total_dBm > self.cca_Threshold_dBm

    def is_radio_busy(self) -> bool:
        return self.transmitting or self.active_session

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