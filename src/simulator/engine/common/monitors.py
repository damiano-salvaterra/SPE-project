# TODO: this module needs to be moved in evaluation somehow
import dataclasses
from typing import List
import pandas as pd

from simulator.engine.common.Monitor import Monitor
from simulator.entities.common.Entity import Entity, EntitySignal
from simulator.entities.protocols.common.packets import MACFrame


class PacketMonitor(Monitor):
    """
    Un monitor che stampa immediatamente le informazioni sui pacchetti
    per il debugging in tempo reale.
    """

    def __init__(self):
        # Non abbiamo più bisogno di memorizzare i record per la stampa finale
        pass

    def update(self, entity: Entity, signal: EntitySignal):
        """
        Chiamato dall'entità. Filtra i segnali relativi ai pacchetti
        e stampa immediatamente le informazioni.
        """
        # Filtra: agisci solo se il segnale contiene un pacchetto
        # if "packet" not in signal.kwargs:
        #    return

        packet = signal.packet
        event_type = signal.event_type

        packet_type = type(packet).__name__
        seqn = getattr(packet, "seqn", "N/A")

        # Safely get addresses
        tx_addr_bytes = getattr(packet, "tx_addr", None)
        rx_addr_bytes = getattr(packet, "rx_addr", None)

        tx_addr = tx_addr_bytes.hex() if isinstance(tx_addr_bytes, bytes) else "N/A"
        rx_addr = rx_addr_bytes.hex() if isinstance(rx_addr_bytes, bytes) else "N/A"

        packet_info = f"Type={packet_type}, Seqn={seqn}, Tx={tx_addr}, Rx={rx_addr}"

        print(
            f"MONITOR [{signal.timestamp:.6f}s] [{entity.host.id}]"
            f" - Event: {event_type}, Packet: {packet_info}"
        )

    def print_log(self):
        # Questo metodo ora non è più necessario per il debug, ma lo lasciamo vuoto
        # per non rompere la compatibilità se venisse chiamato.
        pass

    def get_dataframe(self) -> pd.DataFrame:
        # La raccolta per il DataFrame non è implementata in questa versione di debug
        print(
            "Attenzione: la raccolta dati per il DataFrame è disabilitata nel monitor di debug in tempo reale."
        )
        return pd.DataFrame()
