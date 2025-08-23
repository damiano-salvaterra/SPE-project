# src/simulator/main.py

import sys
import os
from typing import Optional


# 1. Trova il percorso assoluto della directory 'src'
# __file__ è il percorso di questo script (main.py)
# os.path.dirname(__file__) è la cartella che lo contiene ('evaluation')
# os.path.join(..., '..') sale di un livello, arrivando a 'src'
#project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

from simulator.engine.Kernel import Kernel
from simulator.environment.geometry import CartesianCoordinate
from simulator.applications.Application import Application
from simulator.entities.protocols.common.packets import NetPacket, Frame_802154
from simulator.engine.common.Event import Event

# ======================================================================================
# 1. DEFINIZIONE DI UN'APPLICAZIONE SEMPLICE PER GENERARE TRAFFICO
# ======================================================================================

# src/evaluation/main.py

class SimpleTrafficApp(Application):
    """
    Un'applicazione basilare che invia un pacchetto a un destinatario specifico
    dopo un ritardo iniziale.
    """
    def __init__(self, host, destination_addr: Optional[bytes] = None):
        super().__init__()
        self.host = host
        self.destination_addr = destination_addr

    def start(self):
        """Metodo chiamato per avviare l'attività dell'applicazione."""
        print(f"[{self.host.context.scheduler.now():.6f}s] [App:{self.host.id}] Applicazione avviata.")
        if self.destination_addr:
            # Schedula l'invio di un pacchetto dopo 1 secondo
            initial_send_time = self.host.context.scheduler.now() + 1.0
            # CORREZIONE: Il callback ora punta al metodo con il nome corretto
            send_event = Event(time=initial_send_time, blame=self, callback=self.generate_traffic)
            self.host.context.scheduler.schedule(send_event)

    # CORREZIONE: Il metodo è stato rinominato da 'send_packet' a 'generate_traffic'
    # per rispettare il contratto della classe base astratta 'Application'.
    def generate_traffic(self):
        """Crea e invia un pacchetto di rete."""
        payload = f"Hello from {self.host.id}".encode('utf-8')
        packet = NetPacket(payload=payload)
        
        print(f"[{self.host.context.scheduler.now():.6f}s] [App:{self.host.id}] Tento di inviare un pacchetto a {self.destination_addr.hex()}.")
        
        # CORREZIONE: Corretto refuso da 'nexthtop' a 'nexthop'.
        self.host.net.send(packet, nexthop=self.destination_addr)

    def receive(self, packet: NetPacket, sender_addr: bytes):
        """Gestisce la ricezione di un pacchetto dal livello di rete."""
        print(f"[{self.host.context.scheduler.now():.6f}s] [App:{self.host.id}] Pacchetto ricevuto da {sender_addr.hex()}: '{packet.payload.decode('utf-8')}'")


# ======================================================================================
# 2. CONFIGURAZIONE E ESECUZIONE DELLA SIMULAZIONE
# ======================================================================================

def run_simulation():
    print("--- Inizio Test di Integrazione del Simulatore ---")

    # --- Creazione del Kernel ---
    kernel = Kernel(root_seed=42)

    # --- Bootstrap dell'ambiente di simulazione ---
    # Parametri tipici per una rete 802.15.4 a 2.4 GHz
    kernel.bootstrap(
        seed=42,
        dspace_step=1,
        dspace_npt=100,
        freq=2.4e9,
        filter_bandwidth=2e6,
        coh_d=50,
        shadow_dev=4.0,
        pl_exponent=2.1,
        d0=1.0,
        fading_shape=1.0 # Nakagami-m=1 -> Rayleigh fading
    )

    # --- Creazione dei Nodi e delle Applicazioni ---
    print("\n--- Creazione dei Nodi ---")
    
    # Indirizzi a 2 byte, come in 802.15.4 short address mode
    addr_node1 = b'\x00\x01'
    addr_node2 = b'\x00\x02'

    # Creiamo le applicazioni. L'app del nodo 1 invierà un pacchetto al nodo 2.
    app1 = SimpleTrafficApp(host=None, destination_addr=addr_node2)
    app2 = SimpleTrafficApp(host=None, destination_addr=None) # Il nodo 2 è solo ricevente

    # Aggiungiamo i nodi al simulatore
    node1 = kernel.add_node(
        node_id="Node1",
        position=CartesianCoordinate(10, 10),
        app=app1,
        linkaddr=addr_node1
    )
    node2 = kernel.add_node(
        node_id="Node2",
        position=CartesianCoordinate(20, 10), # a 10 metri di distanza
        app=app2,
        linkaddr=addr_node2
    )

    # Colleghiamo l'host all'app dopo la creazione del nodo (importante!)
    app1.host = node1
    app2.host = node2

    # Avviamo le applicazioni (che scheduleranno i primi eventi)
    app1.start()
    app2.start()

    # --- Esecuzione della Simulazione ---
    print("\n--- Inizio Esecuzione Simulazione ---")
    kernel.run(until=5.0) # Esegui per 5 secondi di tempo simulato

    print("\n--- Fine Simulazione ---")
    print(f"Tempo di simulazione finale: {kernel.context.scheduler.now():.6f}s")
    print(f"Numero di eventi rimasti in coda: {kernel.context.scheduler.get_queue_length()}")


if __name__ == "__main__":
    run_simulation()