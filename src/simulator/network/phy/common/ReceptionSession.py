from entities.physical.devices.Node import Node
from network.phy.common.Transmission import Transmission

'''This class implements the observer of the wireless channel
when a node starts receiving a packet. This object has no particular domain meaning (for now):
it is only a utiliy object to observing the evolving state in the wireless channel during the reception
'''
class ReceptionSession:
    def __init__(self, rx_node: Node, capturing_tx: Transmission, start_time: float, end_time: float):
        self.rx_node = rx_node
        self.capturing_tx = capturing_tx
        self.start_time = start_time
        self.end_time = end_time

    def notify_tx_start(self, transmission: Transmission):
        pass

    def notify_tx_end(self, transmission: Transmission):
        pass