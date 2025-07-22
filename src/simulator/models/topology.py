import numpy as np
from numpy.typing import NDArray
from typing import Tuple, List

'''support class for coordinates'''
class CartesianCoordinate:
    def __init__(self, x: np.float64, y: np.float64) -> None:
        self.x = x
        self.y = y

    def to_tuple(self) -> Tuple[np.float64, np.float64]:
        '''
        Returns the Cartesian coordinates as a tuple (x, y)
        '''
        return self.x, self.y
    


'''
This class implements the discrete space grid and gives a n interfece
to convert matrix indeces to space coordinates
'''
class DSpace:

    def __init__(self, dspace_step : int, dspace_npt: int) -> None:
        self.step = dspace_step  # Step size in the discrete space
        self.npt = dspace_npt  # number of points per dimension of discrete the space
        self._size = self.npt * self.step 

        self._create_dspace_grid() # create discrete space


    def _create_dspace_grid(self) -> None:
        half_n = self.npt // 2
        self.x_1d = self.step * np.arange(-half_n, self.npt - half_n)
        self.y_1d = self.step * np.arange(-half_n, self.npt - half_n)
        self.X, self.Y = np.meshgrid(self.x_1d, self.y_1d) # create the grid by cartesian product
                                # X is the matrix of x coordinates, Y the matrix of y coordinates
                                # to access the grid point (i,j)'s space coordinates we need to to do
                                # x = X[i,j] and y = Y[i,j]

        
    def get_axes_1d(self) -> Tuple[NDArray[np.float64], NDArray[np.float64]]:
        '''
        Returns the 1D arrays representing the x and y axes coordinates
        of the discrete space grid
        '''
        return self.x_1d, self.y_1d


    def find_nearest_grid_index(self, P: CartesianCoordinate) -> Tuple[int, int]:
        '''
        Returns the indices of the nearest grid point
        on the shadowing map. P is a tuple containing the (x,y) real-world coordinates
        '''
        # Convert real-world coordinates to grid indices
        x = P.x
        y = P.y
        i = round((y + self._size / 2) / self.step)
        j = round((x + self._size / 2) / self.step)

        # Ensure indices are within bounds
        i = np.clip(i, 0, self.npt - 1)
        j = np.clip(j, 0, self.npt - 1)

        return i, j
    

    def to_cartesian_coordinates(self, i: int, j: int) -> CartesianCoordinate:
        '''
        Given grid indices (i, j), returns the corresponding real-world Cartesian coordinates (x, y)
        '''
        # Ensure indices are within bounds
        i = np.clip(i, 0, self.npt - 1)
        j = np.clip(j, 0, self.npt - 1)

        # Convert grid indices to real-world coordinates
        x = j * self.step - self._size / 2
        y = i * self.step - self._size / 2

        return CartesianCoordinate(x,y)


    def distance(self, P1: CartesianCoordinate, P2: CartesianCoordinate) -> float:
        '''
        Calculates the Euclidean distance between two Cartesian coordinates P1 and P2
        '''
        return np.sqrt((P2.x - P1.x) ** 2 + (P2.y - P1.y) ** 2)
    

'''This class implements the network topology and provides methods
to set up the links. The topology is abstracted as a graph with an adjacency matrix.
'''
class Topology:

    def __init__(self) -> None:
        self.adjacency_matrix: List[List[int]] = []  # Adjacency matrix
        self.node_coordinates: dict[int, CartesianCoordinate] = {}  # to store node coordinates. Key: node ID, Value: CartesianCoordinate
        self.node_ids: List[int] = []  # keep track of node IDs

    def add_node(self, node_id: int, coordinate: CartesianCoordinate) -> None:
        '''
        Adds a node with a given ID and Cartesian coordinate
        '''
        if node_id in self.node_ids:
            raise ValueError(f"Node {node_id} already exists")
        
        self.node_ids.append(node_id)
        self.node_coordinates[node_id] = coordinate

        # update adjacency matrix
        for row in self.adjacency_matrix: # add a column for the node
            row.append(0)
        self.adjacency_matrix.append([0] * len(self.node_ids)) # add a row for the node


    def remove_node(self, node_id: int) -> None:
        '''
        Removes a node from the topology by its ID
        '''
        if node_id not in self.node_ids:
            raise ValueError(f"Node {node_id} does not exist")
        
        idx = self.node_ids.index(node_id)
        self.node_ids.pop(idx)
        self.node_coordinates.pop(node_id)

        # remove row and column from the adjacency matrix
        self.adjacency_matrix.pop(idx)
        for row in self.adjacency_matrix:
            row.pop(idx)


    def add_link(self, node1_id: int, node2_id: int) -> None:
        '''
        Adds a link between two nodes
        '''
        if node1_id not in self.node_ids or node2_id not in self.node_ids:
            raise ValueError("Both nodes must exist in the topology")
        
        idx1 = self.node_ids.index(node1_id)
        idx2 = self.node_ids.index(node2_id)

        self.adjacency_matrix[idx1][idx2] = 1
        self.adjacency_matrix[idx2][idx1] = 1  # Undirected graph


    def remove_link(self, node1_id: int, node2_id: int) -> None:
        '''
        Removes a link between two nodes
        '''
        if node1_id not in self.node_ids or node2_id not in self.node_ids:
            raise ValueError("Both nodes must exist in the topology")
        
        idx1 = self.node_ids.index(node1_id)
        idx2 = self.node_ids.index(node2_id)

        self.adjacency_matrix[idx1][idx2] = 0
        self.adjacency_matrix[idx2][idx1] = 0  # Undirected graph


    def get_neighbors(self, node_id: int) -> List[int]:
        '''
        Returns a list of neighbors for a given node
        '''
        if node_id not in self.node_ids:
            raise ValueError(f"Node {node_id} does not exist")
        
        idx = self.node_ids.index(node_id) #get data structure index of the node
        neighbors = []
        for i, val in enumerate(self.adjacency_matrix[idx]): # iterate over the associated row of the adjacency matrix
            if val != 0:
                neighbors.append(self.node_ids[i])
        return neighbors
    

    def get_node_coordinate(self, node_id: int) -> CartesianCoordinate:
        '''
        Returns the Cartesian coordinate of a node
        '''
        if node_id in self.node_coordinates:
            return self.node_coordinates[node_id]
        raise ValueError(f"Node {node_id} does not exist in the topology")
    
