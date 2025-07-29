
from typing import List, Dict

from environment.propagation.narrowband import NarrowbandChannelModel
from network.phy.common.phy_events import PhyTxEndEvent, PhyTxStartEvent, PhyRxStartEvent, PhyRxEndEvent
from network.phy.common.ReceptionSession import ReceptionSession
from network.phy.common.Transmission import Transmission
from network.common.packets import Packet802_15_4
from entities.physical.devices.Node import Node
from engine.common.SimulationContext import SimulationContext
'''
This class manages the transmissions and the observation of them to monitor collisions'''
class WirelessChannel:
    def __init__(self, propagation_model: NarrowbandChannelModel, nodes: List[Node], context: SimulationContext):
        self.propagation_model = propagation_model
        self.nodes = nodes # list of nodes in the environment
        self.listeners: List[ReceptionSession] = [] # list of subscribers tha to observe the channel, subscibed by PhyLayer
        self.context = context
        self.active_transmissions: Dict[Node, Transmission] # list of currently active transmissions, indexed by the source


    def on_phy_tx_start_event(self, event: PhyTxStartEvent):
        '''
        This functions handles the transmission start event from any node.
        It looks innocent but this is the core of all the phy layer circus: it implicitly treat every transmission as broadcast (wireless=broadcast)
        and registers the active transmissions, notifying the listeners of the state change. This observer pattern allow us to monitor the collisions
        and in general the SINR happening in the channel during a reception attempt by any node: The channel is modified in its entirety when a transmission happen,
        regardless of the destination, so we need a way to make the tranmission to a node susceptible to any other tranmisssion to any other node.
        This function orchestrate this.
        '''
        self.active_transmissions[event.transmission.transmitter] = event.transmission
        transmitter_position = event.transmission.transmitter.position
        for receiver in self.nodes: # compute propagation delay to each node and schedule a reception event for each
                                # (no matters if the transmission is for a specific node, wireless channel is broadcast by nature,
                                # we need this to compute the SINR later)

            if receiver is not event.transmission.transmitter:
                propagation_delay = self.propagation_model.propagation_delay(transmitter_position,
                                                                             receiver.position)
                #schedule reception
                start_time = event.time + propagation_delay
                end_time = start_time + Packet802_15_4.packet_max_gross_duration
                rx_start_event = PhyRxStartEvent(transmission=event.transmisison, time = start_time, callback = receiver.phy.on_phy_rx_start_event)
                rx_end_event = PhyRxEndEvent(transmission=event.transmission, time = end_time, callback = receiver.py.on_phy_rx_end_event)
                self.context.scheduler.schedule(rx_start_event)
                self.context.scheduler.schedule(rx_end_event)

        for listener in self.listeners:
            listener.notify_tx_start(event.transmission) #notify the observers


    def on_tx_end_event(self, event: PhyTxEndEvent):
        self.active_transmissions.pop(event.transmission.transmitter) # remove the transmission from the current transmissions
        for listener in self.listeners:
            listener.notify_tx_start(event.transmission) #notify the observers



    def _subscribe_listener(self, session: ReceptionSession):
        '''
        This function subscribes an observer object of the wireless channel.
        This way, we can easily update and notify the observer objects of new interferers/state change of the wireless channel.
        When the transmission ends, we detach the object and compute the reception/collision probability
        TODO: check if it makes more sense to attach PhyLayer objects (of Node) instead of this
        '''
        self.listeners.append(session)