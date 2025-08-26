
from typing import List, Dict

from simulator.environment.propagation.narrowband import NarrowbandChannelModel
from simulator.entities.common.Entity import Entity
from simulator.entities.protocols.phy.common.phy_events import PhyTxEndEvent, PhyTxStartEvent, PhyRxStartEvent, PhyRxEndEvent
from simulator.entities.protocols.phy.common.ReceptionSession import ReceptionSession
from simulator.entities.protocols.phy.common.Transmission import Transmission
from simulator.entities.protocols.common.packets import MACFrame
from simulator.entities.physical.devices.nodes import StaticNode
from simulator.engine.common.SimulationContext import SimulationContext
'''
This class manages the transmissions and the observation of them to monitor collisions'''
class WirelessChannel(Entity): # TODO: make this class a singleton
    def __init__(self, propagation_model: NarrowbandChannelModel, nodes: List[StaticNode], context: SimulationContext):
        Entity.__init__(self)
        self.propagation_model = propagation_model
        self.nodes = nodes # list of nodes in the environment
        #self.listeners: Dict[StaticNode, ReceptionSession] = {} # dict of subscribers tha to observe the channel, subscibed by PhyLayer
        self.context = context
        self.active_transmissions: Dict[StaticNode, Transmission] = {} # list of currently active transmissions, indexed by the source
        self.tx_counter = 0 # transmission id


    def on_PhyTxStartEvent(self, transmission: Transmission):
        '''
        This functions handles the transmission start event from any node.
        It looks innocent but this is the core of all the phy layer circus: it implicitly treat every transmission as broadcast (wireless=broadcast)
        and registers the active transmissions, notifying the listeners of the state change. This observer pattern allow us to monitor the collisions
        and in general the SINR happening in the channel during a reception attempt by any node: The channel is modified in its entirety when a transmission happen,
        regardless of the destination, so we need a way to make the tranmission to a node susceptible to any other tranmisssion to any other node.
        This function orchestrate this.
        '''
        self.active_transmissions[transmission.transmitter] = transmission
        transmission.unique_id = self.tx_counter # assign an ID to the transmission
        self.tx_counter += 1 # increment counter
        transmitter_position = transmission.transmitter.position
        for receiver in self.nodes: # compute propagation delay to each node and schedule a reception event for each
                                # (no matters if the transmission is for a specific node, wireless channel is broadcast by nature,
                                # we need this to compute the SINR later)

            if receiver is not transmission.transmitter:
                propagation_delay = self.propagation_model.propagation_delay(transmitter_position, receiver.position)
                #schedule reception
                start_rx_time = self.context.scheduler.now() + propagation_delay
                end_rx_time = start_rx_time + transmission.packet.on_air_duration
                rx_start_event = PhyRxStartEvent(time = start_rx_time, blame=self, callback = receiver.phy.on_PhyRxStartEvent, transmission=transmission)
                rx_end_event = PhyRxEndEvent(time = end_rx_time, blame=self, callback = receiver.phy.on_PhyRxEndEvent, transmission=transmission)
                self.context.scheduler.schedule(rx_start_event)
                self.context.scheduler.schedule(rx_end_event)

            #    # if this receiver has an active session, notify it
            #    if receiver in self.listeners.keys():
            #        self.listeners[receiver].notify_tx_start(transmission, propagation_delay) #TODO: i am messing with the future here, maybe i should move the listener to the phy layer and let it manage it from there

        #for listener in self.listeners:
        #    if listener.capturing_tx is not transmission: #in theory, never happens
        #        receiver = listener.receiving_node
        #        propagation_delay = self.propagation_model.propagation_delay(transmitter_position, receiver.position) # notify with propagation delay
        #        listener.notify_tx_start(transmission, propagation_delay) #notify the observers.


    def on_PhyTxEndEvent(self, transmission: Transmission):
        self.active_transmissions.pop(transmission.transmitter) # remove the transmission from the current transmissions
        #for session in self.listeners.values():
        #    if session.receiving_node != transmission.transmitter:
        #        session.notify_tx_end(transmission) #notify the observers



    #def subscribe_listener(self, session: ReceptionSession):
    #    '''
    #    This function subscribes an observer object of the wireless channel.
    #    This way, we can easily update and notify the observer objects of new interferers/state change of the wireless channel.
    #    When the transmission ends, we detach the object and compute the reception/collision probability
    #    TODO: check if it makes more sense to attach PhyLayer objects (of Node) instead of this
    #    '''
    #    self.listeners[session.receiving_node] = session
#
    #def unsubscribe_listener(self, session: ReceptionSession):
    #    self.listeners.pop(session.receiving_node)



    def get_linear_noise_floor(self) -> float:
        '''
        returns the noise floor in linear scale (Watts)
        '''
        return self.propagation_model.dBm_to_watts(self.propagation_model.noise_floor_deterministic())

        


    def get_linear_link_budget(self, node1: StaticNode, node2: StaticNode, tx_power_dBm: float) -> float:
        '''
        returns the link budget in linear scale (Watts)
        '''
        return self.propagation_model.dBm_to_watts(self.propagation_model.link_budget(node1.position, node2.position, Pt_dBm = tx_power_dBm))
        