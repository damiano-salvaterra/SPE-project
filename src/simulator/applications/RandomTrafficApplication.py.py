
from simulator.applications.Application import Application
from simulator.applications.common.app_events import AppSendEvent, AppWaitNetworkBootEvent
#from simulator.entities.physical.devices.nodes import StaticNode
from typing import Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from simulator.entities.physical.devices.nodes import StaticNode

class RandomTrafficApplication(Application):
    '''
    An application that generates network traffic to random destinations
    with exponentially distributed inter-arrival times (a Poisson process).
    '''
    def __init__(self, host: "StaticNode", nodes: Dict[str, bytes], mean_interarrival_time: float):
        super().__init__()
        self.host = host
        self.destinations:  Dict[str, bytes] = {id : addr for id, addr in nodes.items if id != self.host.id}    # dictionary of destinations string_id : linkaddr     

        self.mean_interarrival_time = mean_interarrival_time
        self.packet_counter = 0
        self.received_payloads = []
        rng_id = f"NODE:{self.host.id}/RANDOM_TRAFFIC_APP"
        self.host.context.random_manager.create_stream(rng_id)
        self.rng = self.host.context.random_manager.get_stream(rng_id)

        self._wait_network_bootstrap()

    

    def _wait_network_bootstrap(self): # wait for some time for the network to be built. Then start generating traffic
        wait_time = 10 # wait 10 seconds
        wait_event_time = self.host.context.scheduler.now() + wait_time
        wait_event = AppWaitNetworkBootEvent(time = wait_event_time, blame = self, callback=self._sc)
        self.host.context.scheduler.schedule(wait_event)


    def _schedule_next_packet(self):
        interarrival_time = self.rng.exponential(scale=self.mean_interarrival_time)
        next_send_time = self.host.context.scheduler.now() + interarrival_time

        send_event = AppSendEvent(time=next_send_time, blame=self, callback=self._send_packet)
        self.host.context.scheduler.schedule(send_event)

    def _send_packet(self):
        if not self.destinations:
            print(f"Node {self.host.id}: No destinations to send traffic to.")
            return
        destination_id = self.rng.choice(lsist(self.destinations.keys())) # choose a random destination
        self._send_packet += 1

        payload = f"App-Node:{self.host.id}--->Node:{destination_id}|SENT_TIME:{self.host.context.scheduler.now()}"

        self.host.net.send(payload=payload, destination=self.destinations[destination_id])


    def receive(self, payload: Any, sender: bytes):
        payload = payload + f"/RECEIVED_TIME:{self.host.context.scheduler.now()}"
