from simulator.entities.protocols.common.Layer import Layer
from simulator.entities.common import Entity
from simulator.entities.protocols.phy.common.phy_events import (
    PhyTxEndEvent,
    PhyTxStartEvent,
    PhyUnsyncEvent,
)
from simulator.entities.protocols.phy.common.Transmission import Transmission
from simulator.entities.protocols.common.packets import (
    MACFrame,
    Frame_802_15_4,
    Ack_802_15_4,
)
from simulator.entities.common import NetworkNode
from numpy import log10
from math import isclose
from typing import Dict, Optional
from enum import Enum, auto


from simulator.entities.physical.media.WirelessChannel import WirelessChannel


class RadioState(Enum):
    """Defines the operational states of the transceiver"""

    IDLE = auto()  # Channel is clear, radio is listening
    BUSY = auto()  # Receiving energy, but not synchronized to a packet
    SYNC = auto()  # Synchronized and actively decoding a specific packet
    TX = auto()  # Transmitting a packet


class SimplePhyLayer(Layer, Entity):
    """
    This class implements the physical layer with a state
    machine model (IDLE, BUSY, SYNC, TX)
    """

    def __init__(self, host: NetworkNode, transmission_power_dBm: float = 0):
        Layer.__init__(self, host=host)
        Entity.__init__(self)
        self.capture_threshold_dB = 5
        self.cca_Threshold_dBm = -85
        self.correlator_threshold = -95
        self.transmission_power_dBm = transmission_power_dBm
        self.transmission_media = None

        # --- state machine control variables ---
        self.state: RadioState = RadioState.IDLE
        self.synchronized_tx: "Transmission" = None
        self.reception_power_state: Dict["Transmission", float] = {}
        self.total_received_power_W: float = 0.0  # currently receiveed power
        self.min_sinr_db_session: float = float("inf")

        # --- State for MAC layer ---
        self._last_seqn = 0
        # self._last_successful_rx_rssi_dBm: float = -150.0

    def connect_transmission_media(self, transmission_media: "WirelessChannel"):
        self.transmission_media = transmission_media

    def on_PhyRxStartEvent(self, transmission: Transmission):
        """Handles the arrival of a new signal at the receiver"""
        # print(f"DEBUG [{self.host.context.scheduler.now():.6f}s] [{self.host.id}] "
        #   f"PhyRxStartEvent triggered by Tx from {transmission.transmitter.id}.")

        received_power_W = self.transmission_media.get_linear_link_budget(
            node1=self.host,
            node2=transmission.transmitter,
            tx_power_dBm=transmission.transmission_power_dBm,
        )

        # If the radio is transmitting, it ignores everything
        if self.state == RadioState.TX:
            return

        # Update the physical state of the channel.
        self.reception_power_state[transmission] = received_power_W
        self.total_received_power_W += received_power_W

        if self.state == RadioState.IDLE:
            # first signal detected: transition from IDLE to a receiving state
            self._attempt_tx_synchronization(transmission, received_power_W)

        elif self.state == RadioState.BUSY:
            # already receiving energy, but the radio is not locked on a transmission: try to sync on this new packet
            self._attempt_tx_synchronization(transmission, received_power_W)

        elif self.state == RadioState.SYNC:
            # Decoder is already locked on a packet: this is interference, so update the
            # minimum SINR of this packet
            self._update_minimum_SINR()

    def on_PhyRxEndEvent(self, transmission: Transmission):
        """Handles the end of a signal on the receiver"""
        if transmission not in self.reception_power_state:
            return  # should not happen, but just in case

        ended_power_W = self.reception_power_state.pop(transmission)
        self.total_received_power_W -= ended_power_W

        if self.state == RadioState.SYNC and self.synchronized_tx == transmission:
            # if the the packet we were decoding has just ended, check if is correctly received and clean up
            self._finalize_rx(power_W=ended_power_W)

        # if the channel is now silent, become IDLE, otherwise, stay BUSY
        if isclose(self.total_received_power_W, 0.0):
            self.state = RadioState.IDLE
        elif self.state != RadioState.TX:
            self.state = RadioState.BUSY

    def on_PhyTxStartEvent(self, transmission: Transmission):
        """Handles the start of a transmission from this node's MAC."""
        self.state = RadioState.TX
        self.synchronized_tx = None  # Cannot be synchronized while transmitting
        self.transmission_media.on_PhyTxStartEvent(transmission=transmission)

    def on_PhyTxEndEvent(self, transmission: Transmission):
        """Handles the end of this node's transmission."""
        self.transmission_media.on_PhyTxEndEvent(transmission=transmission)
        self.host.rdc.on_PhyTxEndEvent(packet=transmission.packet)

        # After transmitting, check the channel state to decide the next state.
        if isclose(self.total_received_power_W, 0.0):
            self.state = RadioState.IDLE
        else:
            self.state = RadioState.BUSY

    def _attempt_tx_synchronization(self, transmission: Transmission, power_W: float):
        """locks the correlator onto the new transmission, if possible"""
        power_dBm = 10 * log10(power_W * 1000) if power_W > 0 else -float("inf")

        if power_dBm >= self.correlator_threshold:
            self.min_sinr_db_session = float(
                "inf"
            )  # reset the SINR tracker, just for robustness
            # because at this point it should be already reset
            self.state = RadioState.SYNC
            self.synchronized_tx = transmission
            self._update_minimum_SINR()
            self._schedule_sync_check(transmission)
        else:
            # the signal is too weak to sync, just go in BUSY state
            self.state = RadioState.BUSY

    def _finalize_rx(self, power_W: float):
        """Called when a synchronized packet ends and decides its fate"""
        is_decoded = self.min_sinr_db_session >= self.capture_threshold_dB

        if is_decoded:
            received_packet = self.synchronized_tx.packet
            rssi_dBm = 10 * log10(power_W * 1000) if power_W > 0 else -150

            sender_addr = self.synchronized_tx.transmitter.linkaddr
            # self._last_successful_rx_rssi_dBm = 10 * log10(power_W * 1000) if power_W > 0 else -150
            self.receive(
                payload=received_packet, sender_addr=sender_addr, rssi=rssi_dBm
            )

        # The decoder is now free
        self.synchronized_tx = None
        self.min_sinr_db_session = float("inf")

    def _update_minimum_SINR(self):
        """Computes the instantaneous SINR and updates the minimum for the current locked transmission"""
        if not self.synchronized_tx:
            return

        noise_floor_W = self.transmission_media.get_linear_noise_floor()
        signal_power_W = self.reception_power_state.get(self.synchronized_tx, 0.0)

        if isclose(signal_power_W, 0.0):
            self.min_sinr_db_session = -float("inf")
            return

        # Interference is the total received power MINUS the signal power.
        interference_power_W = self.total_received_power_W - signal_power_W

        sinr = signal_power_W / (noise_floor_W + interference_power_W)
        current_sinr_db = 10 * log10(sinr) if sinr > 0 else -float("inf")

        if current_sinr_db < self.min_sinr_db_session:
            self.min_sinr_db_session = current_sinr_db

    def _schedule_sync_check(self, transmission: "Transmission"):
        """helper to schedule the moment in which the decoder understands if the packet is of interest or not: if is
        not of interest, the decoder is desynchronized from the transmission and go in busy state, ready to receive something
        more interesting"""
        if isinstance(transmission.packet, Ack_802_15_4):
            is_for_me = transmission.packet.seqn == self._last_seqn
            detection_time = (
                self.host.context.scheduler.now()
                + transmission.packet.ack_detection_time
            )
            if not is_for_me:
                unsync_event = PhyUnsyncEvent(
                    time=detection_time, blame=self, callback=self._unsynchronize
                )
                self.host.context.scheduler.schedule(unsync_event)
        elif isinstance(transmission.packet, Frame_802_15_4):
            is_for_me = (
                transmission.packet.rx_addr == self.host.linkaddr
                or transmission.packet.rx_addr == Frame_802_15_4.broadcast_linkaddr
            )
            detection_time = (
                self.host.context.scheduler.now()
                + transmission.packet.daddr_detection_time
            )
            if not is_for_me:
                unsync_event = PhyUnsyncEvent(
                    time=detection_time, blame=self, callback=self._unsynchronize
                )
                self.host.context.scheduler.schedule(unsync_event)

    def _unsynchronize(self):
        """Transitions from SYNC to BUSY because the packet is not for me"""
        if self.state == RadioState.SYNC:
            self.synchronized_tx = None
            self.min_sinr_db_session = float("inf")
            self.state = RadioState.BUSY

    # ----- Interface for upper layers

    def send(self, payload: MACFrame, destination: Optional[bytes] = None):

        if isinstance(payload, Frame_802_15_4):
            self._last_seqn = payload.seqn

        transmission = Transmission(self.host, payload, self.transmission_power_dBm)

        start_time = (
            self.host.context.scheduler.now() + 1e-12
        )  # just to make the 2 events have different simulation times, it shouldnt be a problem
        # a problem anyways since the other event is already popped, but just for robustness we add a negligible delay
        end_time = start_time + payload.on_air_duration

        # shcedule events
        tx_start_event = PhyTxStartEvent(
            time=start_time,
            blame=self,
            callback=self.on_PhyTxStartEvent,
            transmission=transmission,
        )
        tx_end_event = PhyTxEndEvent(
            time=end_time,
            blame=self,
            callback=self.on_PhyTxEndEvent,
            transmission=transmission,
        )

        self.host.context.scheduler.schedule(tx_start_event)
        self.host.context.scheduler.schedule(tx_end_event)

    def cca_802154_Mode1(self) -> bool:
        """checks the power currently in the channel. If the power is over the threshold, returns True ( channel busy)"""
        total_power_dBm = (
            10 * log10(self.total_received_power_W * 1000)
            if self.total_received_power_W > 0
            else -float("inf")
        )
        return total_power_dBm > self.cca_Threshold_dBm

    def is_radio_busy(self) -> bool:
        """The radio is busy if it's not in the IDLE state"""
        return self.state != RadioState.IDLE

    def receive(self, payload: MACFrame, sender_addr: bytes, rssi: float):
        # print(f">>> DEBUG-PHY [{self.host.id}]: receive() called with RSSI = {rssi:.2f} dBm")
        
        self.host.rdc.receive(payload=payload, sender_addr=sender_addr, rssi=rssi)

    # def get_last_rssi(self) -> float:
    #    return self._last_successful_rx_rssi_dBm #NOTE:check if this variable may unexpectedly change due to some race condition or weird situation
