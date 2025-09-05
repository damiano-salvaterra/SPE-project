from simulator.entities.common.Entity import EntitySignal
from simulator.entities.protocols.common.packets import MACFrame


# TODO: this file needs to be moved in evaluation somehow


class PacketSignal(EntitySignal):
    """
    Un segnale specifico per notificare eventi legati a pacchetti (invio, ricezione).
    Contiene il pacchetto stesso come informazione aggiuntiva.
    """

    def __init__(
        self, descriptor: str, timestamp: float, event_type: str, packet: MACFrame
    ):
        # Il descriptor può essere usato per descrivere l'evento, es. "PacketSent"
        super().__init__(descriptor=descriptor, timestamp=timestamp)
        self.event_type = event_type
        self.packet = packet
