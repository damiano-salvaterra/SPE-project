import pandas as pd
from typing import TYPE_CHECKING

from simulator.engine.common.monitor import Monitor
from evaluation.signals.tarp_signals import (
    TARPUnicastSendSignal,
    TARPForwardingSignal,
    TARPUnicastReceiveSignal,
    TARPDropSignal,
    TARPBroadcastSendSignal,
    TARPBroadcastReceiveSignal,
    TARPParentChangeSignal
)

# Avoid circular import issues at type-checking time
if TYPE_CHECKING:
    from simulator.entities.common import Entity, EntitySignal


class TARPMonitor(Monitor):
    """
    Monitor that tracks TARP protocol events (send, receive, forward, drop, etc.).
    Inherits from BaseMonitor to log structured data.
    """

    def __init__(self, verbose=True):
        super().__init__(verbose=verbose)

    def update(self, entity: "Entity", signal: "EntitySignal"):
        """
        Called by the TARP entity when a signal is emitted.
        Filters for specific TARP signals and logs them.
        """
        # TARP signals are emitted by TARPProtocol, which is on a host.
        try:
            current_time = signal.timestamp
            node_id = entity.host.id
            log_entry = {"time": current_time, "node_id": node_id}
            print_msg = None
        except AttributeError:
            return

        if isinstance(signal, TARPUnicastSendSignal):
            log_entry.update({
                "event": "UC_SEND",
                "type": signal.packet_type,
                "dest": signal.destination.hex()
            })
            print_msg = f"Send {signal.packet_type} to {signal.destination.hex()}"

        elif isinstance(signal, TARPForwardingSignal):
            log_entry.update({
                "event": "FORWARD",
                "type": signal.packet_type,
                "from": signal.received_from.hex(),
                "to": signal.forwarding_to.hex(),
                "orig_src": signal.original_source.hex(),
                "final_dest": signal.destination.hex()
            })
            print_msg = f"Forward {signal.packet_type} from {signal.received_from.hex()} to {signal.forwarding_to.hex()} (dest: {signal.destination.hex()})"

        elif isinstance(signal, TARPUnicastReceiveSignal):
            log_entry.update({
                "event": "UC_RECV",
                "type": signal.packet_type,
                "from": signal.received_from.hex(),
                "orig_src": signal.original_source.hex()
            })
            # Add special parsing for REPORT content
            if signal.packet_type == "UC_TYPE_REPORT":
                try:
                    # The descriptor contains the report content
                    report_content = signal.descriptor.split("content:")[1].strip()
                    log_entry["report_content"] = report_content
                    print_msg = f"Recv REPORT from {signal.received_from.hex()} (content: {report_content})"
                except (IndexError, AttributeError):
                    print_msg = f"Recv {signal.packet_type} from {signal.received_from.hex()} (orig: {signal.original_source.hex()})"
            else:
                 print_msg = f"Recv {signal.packet_type} from {signal.received_from.hex()} (orig: {signal.original_source.hex()})"


        elif isinstance(signal, TARPDropSignal):
            # --- MODIFICA ---
            # Il descriptor del segnale è già un messaggio di log leggibile
            # formattato all'interno di TARP.py.
            # Rimuoviamo il parsing fragile e usiamo il descriptor.
            
            # Semplifichiamo l'estrazione della ragione per il log dei dati
            reason_simple = "No Route" # Default
            if "unknown sender" in signal.descriptor:
                reason_simple = "Unknown Sender"
            
            log_entry.update({
                "event": "DROP",
                "type": signal.packet_type,
                "dest": signal.destination.hex(),
                "reason": reason_simple, # Log di una categoria semplice
                "details": signal.descriptor # Log del messaggio completo
            })
            
            # Stampa l'intero descriptor, che contiene già il motivo.
            # Rimuoviamo il prefisso "[Node-X] " perché il monitor lo aggiunge già.
            print_msg = signal.descriptor.split("] ", 1)[-1]
            # --- FINE MODIFICA ---

        elif isinstance(signal, TARPBroadcastSendSignal):
            # The descriptor has critical info not in the signal object.
            details = "BEACON"
            try:
                details = signal.descriptor.split("beacon:")[1].strip()
            except Exception:
                pass

            log_entry.update({
                "event": "BC_SEND",
                "type": "BEACON",
                "details": details
            })
            print_msg = f"Sent BEACON ({details})"

        elif isinstance(signal, TARPBroadcastReceiveSignal):
            log_entry.update({
                "event": "BC_RECV",
                "type": "BEACON",
                "source": signal.source.hex(),
                "rssi": signal.rssi
            })
            print_msg = f"Recv BEACON from {signal.source.hex()}, rssi: {signal.rssi}"

        elif isinstance(signal, TARPParentChangeSignal):
            old_parent_hex = signal.old_parent.hex() or "None"
            new_parent_hex = signal.new_parent.hex() or "None"
            log_entry.update({
                "event": "PARENT_CHANGE",
                "old_parent": old_parent_hex,
                "new_parent": new_parent_hex
            })
            print_msg = f"Parent change: {old_parent_hex} -> {new_parent_hex}"

        else:
            # Ignore other signals
            return

        self.log.append(log_entry)

        if self.verbose and print_msg:
            # L'ID del nodo è ora aggiunto esternamente
            print(f"[TARP_MONITOR] [{current_time:.6f}s] [{node_id}] {print_msg}")