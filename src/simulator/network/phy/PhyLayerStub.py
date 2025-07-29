class PhyLayerStub:
    def __init__(self, channel, address):
        self.channel = channel
        self.address = address

    def send(self, packet):
        """Inoltra il packet al canale così com’è."""
        self.channel.transmit(packet, sender=self.address)

    def on_receive(self, packet):
        """Viene chiamato dal canale quando arriva un packet destinato a questo nodo."""
        # semplicemente passiamo il packet al MAC
        self.mac.receive(packet)
