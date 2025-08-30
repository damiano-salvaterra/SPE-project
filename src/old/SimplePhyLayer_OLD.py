from simulator.entities.protocols.common.Layer import Layer
from simulator.entities.common.Entity import Entity
from simulator.engine.common.signals import PacketSignal
from simulator.entities.protocols.phy.common.phy_events import PhyTxEndEvent, PhyTxStartEvent, PhyPacketTypeDetectionEvent, PhyDaddrDetectionEvent
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
        self.synchronized_tx = None
        
        ### CHANGE: Add a dictionary to store the state (power in Watts) of all current receptions.
        self.reception_power_state: Dict["Transmission", float] = {}

        self._last_seqn = 0
        self._last_successful_rx_rssi_dBm: float = -150.0

    def connect_transmission_media(self, transmission_media: "WirelessChannel"):
        self.transmission_media = transmission_media

    def _is_decoded(self, session: "ReceptionSession"):
        """
        Computes SINR using the pre-sampled power values stored in self.reception_power_state.
        This method is now deterministic as it no longer samples the channel.
        """
        noise_floor_linear = self.transmission_media.get_linear_noise_floor()
        
        ### CHANGE: Get the main signal's power from our state dictionary.
        capturing_tx_power_linear = self.reception_power_state.get(session.capturing_tx, 0.0)
        
        print(f"\n--- DEBUG: _is_decoded on Node {self.host.id} at t={self.host.context.scheduler.now():.6f}s ---")
        print(f"  - Capturing TX from: {session.capturing_tx.transmitter.id}")
        print(f"  - Signal Power (Linear): {capturing_tx_power_linear:.4e} W")
        print(f"  - Noise Floor (Linear): {noise_floor_linear:.4e} W")


        if not session.reception_segments or capturing_tx_power_linear == 0.0:
            print("  - DECODING FAILED: No reception segments or zero signal power.")
            print("------------------------------------------------------------------\n")
            return False

        segments_SINR = []
        for i, segment in enumerate(session.reception_segments):
            ### CHANGE: Sum the powers of interferers by looking them up in our state dictionary.
            interferers_power = sum(
                self.reception_power_state.get(tx, 0.0) for tx in segment.interferers
            )
            segment_SINR = capturing_tx_power_linear / (noise_floor_linear + interferers_power)
            segments_SINR.append(segment_SINR)
            print(f"  - Segment {i}:")
            print(f"    - Interferers Power (Linear): {interferers_power:.4e} W")
            print(f"    - SINR (Linear): {segment_SINR:.4e}")

        min_SINR = min(segments_SINR)
        min_SINR_dB = 10 * log10(min_SINR) if min_SINR > 0 else -float('inf')

        result = min_SINR_dB >= self.capture_threshold_dB
        print(f"  - Min SINR: {min_SINR_dB:.2f} dB")
        print(f"  - Capture Threshold: {self.capture_threshold_dB} dB")
        print(f"  - DECODING RESULT: {'SUCCESS' if result else 'FAILURE'}")
        print("------------------------------------------------------------------\n")
        
        return result

    def on_PhyRxStartEvent(self, transmission: Transmission):
        """
        Samples the channel ONCE for the new transmission and stores its power.
        """
        ### CHANGE: Sample channel once and convert to dBm for logging/comparison.
        received_power_linear = self.transmission_media.get_linear_link_budget(
            node1=self.host, node2=transmission.transmitter, tx_power_dBm=transmission.transmission_power_dBm
        )
        received_power_dBm = 10 * log10(received_power_linear * 1000)
        
        ### CHANGE: Store the sampled linear power in our state dictionary.
        self.reception_power_state[transmission] = received_power_linear

        print("_____________________________________________")
        print(f"[{self.host.context.scheduler.now():.6f}s] [PHY/{self.host.id}] Signal detected from {transmission.transmitter.id}. "
              f"RSSI: {received_power_dBm:.2f} dBm. "
              f"Sensitivity: {self.correlator_threshold:.2f} dBm.", flush=True)
        print("_____________________________________________")

        ### CHANGE: Perform comparison in dBm domain.
        if received_power_dBm < self.correlator_threshold:
            # Signal is too weak to be considered further. Clean up its state.
            del self.reception_power_state[transmission]
            return

        if self.active_session:
            self.last_session.notify_tx_start(transmission=transmission)
        else:
            self._open_session(transmission)
            self.synchronized_tx = transmission

        # Logic for packet type/address detection remains the same
        if self.synchronized_tx == transmission:
            if isinstance(transmission.packet, Ack_802154):
                pending_ack = (transmission.packet.seqn == self._last_seqn)
                type_detection_time = self.host.context.scheduler.now() + transmission.packet.ack_detection_time
                close_session = not pending_ack
                callback = self._close_session if close_session else None
                type_detection_event = PhyPacketTypeDetectionEvent(time=type_detection_time, blame=self, callback=callback)
                self.host.context.scheduler.schedule(type_detection_event)
            elif isinstance(transmission.packet, Frame_802154):
                this_destination = (transmission.packet.rx_addr == self.host.linkaddr or
                                    transmission.packet.rx_addr == Frame_802154.broadcast_linkaddr)
                daddr_detection_time = self.host.context.scheduler.now() + transmission.packet.daddr_detection_time
                close_session = not this_destination
                callback = self._close_session if close_session else None
                daddr_detection_event = PhyDaddrDetectionEvent(time=daddr_detection_time, blame=self, callback=callback)
                self.host.context.scheduler.schedule(daddr_detection_event)

    def on_PhyRxEndEvent(self, transmission: Transmission):
        """
        Handles the end of a packet reception, using stored state for consistency.
        """
        # Clean up the state for the transmission that just ended, regardless of what happens next.
        ### CHANGE: Remove the ended transmission from our power state dictionary.
        ended_tx_power_linear = self.reception_power_state.get(transmission, None)

        if self.active_session and self.synchronized_tx == transmission:
            received_packet = self.last_session.capturing_tx.packet
            is_decoded = self._is_decoded(self.last_session)
            self._close_session()

            if is_decoded and ended_tx_power_linear is not None:
                rssi_dBm = 10 * log10(ended_tx_power_linear * 1000)
                self._last_successful_rx_rssi_dBm = rssi_dBm
                print("_____________________________________________")
                print(f"[{self.host.context.scheduler.now():.6f}s] [PHY/{self.host.id}] PACKET DECODED SUCCESSFULLY from {transmission.transmitter.id}", flush=True)
                print("_____________________________________________")
                
                self.receive(payload=received_packet)
            else:
                print("_____________________________________________")
                print(f"[{self.host.context.scheduler.now():.6f}s] [PHY/{self.host.id}] PACKET LOST (DECODING FAILED) from {transmission.transmitter.id}", flush=True)
                print("_____________________________________________")

        elif self.active_session and self.synchronized_tx != transmission:
            self.last_session.notify_tx_end(transmission=transmission)

    def _open_session(self, transmission: Transmission):
        from simulator.entities.protocols.phy.common.ReceptionSession import ReceptionSession
        
        ### CHANGE: Sample power for any pre-existing interferers and add to state.
        # Note: The main transmission's power is already in the state dictionary from on_PhyRxStartEvent.
        for tx in self.transmission_media.active_transmissions.values():
            if tx not in self.reception_power_state and tx.transmitter is not self.host:
                interferer_power = self.transmission_media.get_linear_link_budget(
                    self.host, tx.transmitter, tx.transmission_power_dBm
                )
                self.reception_power_state[tx] = interferer_power
        
        # Get the list of interferers for the session object.
        current_interferers = [
            tx for tx in self.transmission_media.active_transmissions.values()
            if tx.transmitter is not self.host and tx is not transmission
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
            self.last_session.end_time = self.host.context.scheduler.now()
            self.active_session = False
            self.synchronized_tx = None
            self.last_session = None
            ### CHANGE: Crucially, clear the entire power state when a session ends.
            self.reception_power_state.clear()
            
    # ... The rest of the methods (on_PhyTxStartEvent, on_PhyTxEndEvent, send, cca, etc.) remain unchanged ...
    def on_PhyTxStartEvent(self, transmission: Transmission):
        self.transmitting = True # radio busy
        self.transmission_media.on_PhyTxStartEvent(transmission=transmission) # notify channel

    def on_PhyTxEndEvent(self, transmission: Transmission):
        self.transmitting = False
        self.transmission_media.on_PhyTxEndEvent(transmission=transmission) # notify channel
        self.host.rdc.on_PhyTxEndEvent(packet=transmission.packet) # notify rdc
        
    def send(self, payload: MACFrame):
        '''
        create transmission and schedule the phy_tx events
        '''
        signal = PacketSignal(
            descriptor="PHY Packet Transmission",
            timestamp=self.host.context.scheduler.now(),
            event_type="PacketSent",
            packet=payload
        )
        self._notify_monitors(signal)


        if isinstance(payload, Frame_802154):
            self._last_seqn = payload.seqn

        transmission = Transmission(transmitter = self.host, packet = payload, transmission_power_dBm = self.transmission_power)
        
        start_tx_time = self.host.context.scheduler.now() + 1e-12
        end_tx_time = start_tx_time + payload.on_air_duration
        tx_start_event = PhyTxStartEvent(time=start_tx_time, blame = self, callback = self.on_PhyTxStartEvent, transmission = transmission)
        tx_end_event = PhyTxEndEvent(time=end_tx_time, blame = self, callback = self.on_PhyTxEndEvent, transmission = transmission)

        self.host.context.scheduler.schedule(tx_start_event)
        self.host.context.scheduler.schedule(tx_end_event)


    def cca_802154_Mode1(self) -> bool:
        """
        CCA must always perform a fresh sample of the channel energy.
        This is correct as it represents an instantaneous measurement.
        """
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
        '''call the RDC'''
        signal = PacketSignal(
            descriptor="PHY Packet Reception",
            timestamp=self.host.context.scheduler.now(),
            event_type="PacketReceived",
            packet=payload
        )
        self._notify_monitors(signal)

        self.host.rdc.receive(payload = payload)

    def get_last_rssi(self) -> float:
        return self._last_successful_rx_rssi_dBm