# src/evaluation/main.py

import sys
import os
from typing import Optional, TYPE_CHECKING
import random

# --- Gestione del Percorso di Python ---
# Aggiunge la directory 'src' al path per permettere gli import assoluti
# quando si esegue con 'python -m evaluation.main' dalla cartella 'src'
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# --- Import del Simulatore ---
from simulator.engine.Kernel import Kernel
from simulator.environment.geometry import CartesianCoordinate
from simulator.applications.Application import Application
from simulator.entities.protocols.common.packets import NetPacket
from simulator.engine.common.Event import Event

if TYPE_CHECKING:
    from simulator.entities.physical.devices.nodes import StaticNode

# ======================================================================================
# APPLICAZIONE DI TEST PER GENERARE TRAFFICO
# ======================================================================================

class SimpleTrafficApp(Application):
    """
    Un'applicazione basilare che invia un pacchetto a un destinatario specifico
    dopo un ritardo iniziale. Questa versione è corretta per funzionare con
    l'architettura attuale del simulatore.
    """
    def __init__(self, host: Optional["StaticNode"], destination_addr: Optional[bytes] = None):
        # 1. Chiama il costruttore della classe base (senza argomenti)
        super().__init__()
        # 2. Imposta gli attributi specifici dell'istanza
        self.host = host
        self.destination_addr = destination_addr

    def start(self):
        """Metodo chiamato per avviare l'attività dell'applicazione."""
        print(f"[{self.host.context.scheduler.now():.6f}s] [App:{self.host.id}] Applicazione avviata.")
        if self.destination_addr:
            # Schedula l'invio di un pacchetto dopo un ritardo
            initial_send_time = self.host.context.scheduler.now() + 5.0 # Aumentato per dare tempo a TARP
            send_event = Event(time=initial_send_time, blame=self, callback=self.generate_traffic)
            self.host.context.scheduler.schedule(send_event)

    def generate_traffic(self):
        """
        Metodo che implementa la logica di generazione del traffico,
        come richiesto dalla classe base astratta 'Application'.
        """
        payload = f"Hello from {self.host.id}".encode('utf-8')
        packet = NetPacket(payload=payload)
        
        print(f"[{self.host.context.scheduler.now():.6f}s] [App:{self.host.id}] Tento di inviare un pacchetto a {self.destination_addr.hex()}.")
        
        # Passa il pacchetto al livello di rete
        self.host.net.send(packet, destination=self.destination_addr)

    def receive(self, packet: NetPacket, sender_addr: bytes):
        """Gestisce la ricezione di un pacchetto dal livello di rete."""
        payload_str = packet.payload.decode('utf-8', errors='ignore')
        print(f"[{self.host.context.scheduler.now():.6f}s] [App:{self.host.id}] Pacchetto ricevuto da {sender_addr.hex()}: '{payload_str}'")


# ======================================================================================
# CONFIGURAZIONE E ESECUZIONE DELLA SIMULAZIONE
# ======================================================================================

def run_simulation():
    print("--- Inizio Test di Integrazione del Simulatore ---")

    # --- Creazione del Kernel ---
    kernel = Kernel(root_seed=42)

    # --- Bootstrap dell'ambiente di simulazione ---
    kernel.bootstrap(
        seed=42,
        dspace_step=1, dspace_npt=100, freq=2.4e9, filter_bandwidth=2e6,
        coh_d=50, shadow_dev=4.0, pl_exponent=2.1, d0=1.0, fading_shape=1.0
    )

    # --- Creazione dei Nodi e delle Applicazioni ---
    print("\n--- Creazione dei Nodi ---")
    
    addr_node1 = b'\x00\x01'
    addr_node2 = b'\x00\x02'

    # Aggiungiamo i nodi al simulatore. L'app verrà creata e assegnata dopo.
    node1 = kernel.add_node(
        node_id="Node1",
        position=CartesianCoordinate(10, 10),
        app=None, # L'app viene assegnata in un secondo momento
        linkaddr=addr_node1
    )
    node2 = kernel.add_node(
        node_id="Node2",
        position=CartesianCoordinate(20, 10), # a 10 metri di distanza
        app=None,
        linkaddr=addr_node2
    )

    # Crea e collega le applicazioni ai nodi.
    # Questo approccio in due passaggi evita problemi di dipendenza durante l'init.
    app1 = SimpleTrafficApp(host=node1, destination_addr=addr_node2)
    node1.app = app1

    app2 = SimpleTrafficApp(host=node2, destination_addr=None) # Il nodo 2 è solo ricevente
    node2.app = app2
    
    # Avviamo le applicazioni (che scheduleranno i primi eventi)
    app1.start()
    app2.start()

    # --- Esecuzione della Simulazione ---
    print("\n--- Inizio Esecuzione Simulazione ---")
    kernel.run(until=15.0) # Esegui per 15 secondi di tempo simulato

    print("\n--- Fine Simulazione ---")
    print(f"Tempo di simulazione finale: {kernel.context.scheduler.now():.6f}s")
    print(f"Numero di eventi rimasti in coda: {kernel.context.scheduler.get_queue_length()}")


if __name__ == "__main__":
    run_simulation()
