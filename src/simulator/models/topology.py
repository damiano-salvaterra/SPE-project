import numpy as np
from numpy.typing import NDArray
from typing import Tuple

'''support class for coordinates'''
class CartesianCoordinate:
    def __init__(self, x: np.float64, y: np.float64) -> None:
        self.x = x
        self.y = y

    def __repr__(self) -> str:
        return f"CartesianCoordinate(x={self.x}, y={self.y})"
    
    def to_tuple(self) -> Tuple[np.float64, np.float64]:
        '''
        Returns the Cartesian coordinates as a tuple (x, y)
        '''
        return self.x, self.y
    


'''This class implements the discrete space grid and the topology of the nodes'''
class Topology:

    def __init__(self, dspace_step : int, dspace_npt: int) -> None:
        self.dspace_step = dspace_step  # Step size in the discrete space
        self.dspace_npt = dspace_npt  # number of points per dimension of discrete the space
        self._size = self.dspace_npt * self.dspace_step 

        self._create_dspace_grid() # create discrete space



    def _create_dspace_grid(self) -> None:
        half_n = self.dspace_npt // 2
        self.x_1d = self.dspace_step * np.arange(-half_n, self.dspace_npt - half_n)
        self.y_1d = self.dspace_step * np.arange(-half_n, self.dspace_npt - half_n)
        self.X, self.Y = np.meshgrid(self.x_1d, self.y_1d) # create the grid by cartesian product
                                # X is the matrix of x coordinates, Y the matrix of y coordinates
                                # to access the grid point (i,j)'s space coordinates we need to to do
                                # x = X[i,j] and y = Y[i,j]
    

    def get_nearest_grid_index(self, P: CartesianCoordinate) -> Tuple[int, int]:
        '''
        Returns the indices of the nearest grid point
        on the shadowing map. P is a tuple containing the (x,y) real-world coordinates
        '''
        # Convert real-world coordinates to grid indices
        x = P.x
        y = P.y
        i = round((y + self._size / 2) / self.dspace_step)
        j = round((x + self._size / 2) / self.dspace_step)

        # Ensure indices are within bounds
        i = np.clip(i, 0, self.dspace_npt - 1)
        j = np.clip(j, 0, self.dspace_npt - 1)

        return i, j
    
    def get_cartesian_coordinates(self, i: int, j: int) -> CartesianCoordinate:
        '''
        Given grid indices (i, j), returns the corresponding real-world Cartesian coordinates (x, y)
        '''
        # Ensure indices are within bounds
        i = np.clip(i, 0, self.dspace_npt - 1)
        j = np.clip(j, 0, self.dspace_npt - 1)

        # Convert grid indices to real-world coordinates
        x = j * self.dspace_step - self._size / 2
        y = i * self.dspace_step - self._size / 2

        return CartesianCoordinate(x,y)

    
    def get_axes_1d(self) -> Tuple[NDArray[np.float64], NDArray[np.float64]]:
        '''
        Returns the 1D arrays representing the x and y axes coordinates
        of the discrete space grid
        '''
        return self.x_1d, self.y_1d





