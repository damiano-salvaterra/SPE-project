from environment.geometry import CartesianCoordinate

class Node():
    def __init__(self, node_id: str, position: CartesianCoordinate):
        self.id = node_id
        self.position = position
    