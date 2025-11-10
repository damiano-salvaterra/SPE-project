import numpy as np
from typing import Tuple
from numpy.typing import NDArray  # static type hints for numpy


"""support class for coordinates"""


class CartesianCoordinate:
    def __init__(self, x: np.float64, y: np.float64) -> None:
        self.x = x
        self.y = y

    def __eq__(self, other: object) -> bool:
        """
        Overloads the equality operator to compare two CartesianCoordinate objects.
        """
        if not isinstance(other, CartesianCoordinate):
            return NotImplemented
        return np.isclose(self.x, other.x) and np.isclose(self.y, other.y)

    def to_tuple(self) -> Tuple[np.float64, np.float64]:
        """
        Returns the Cartesian coordinates as a tuple (x, y)
        """
        return self.x, self.y


"""
This class implements the discrete space grid and gives a n interfece
to convert matrix indeces to space coordinates
"""


class DSpace:
    def __init__(self, dspace_step: int, dspace_npt: int) -> None:
        self.step = dspace_step  # Step size in the discrete space
        self.npt = dspace_npt  # number of points per dimension of discrete the space
        self._size = self.npt * self.step
        self._create_dspace_grid()  # create discrete space

    def _create_dspace_grid(self) -> None:
        half_n = self.npt // 2
        self.x_1d = self.step * np.arange(-half_n, self.npt - half_n)
        self.y_1d = self.step * np.arange(-half_n, self.npt - half_n)
        self.X, self.Y = np.meshgrid(
            self.x_1d, self.y_1d
        )  # create the grid by cartesian product
        # X is the matrix of x coordinates, Y the matrix of y coordinates
        # to access the grid point (i,j)'s space coordinates we need to to do
        # x = X[i,j] and y = Y[i,j]

    def get_axes_1d(self) -> Tuple[NDArray[np.float64], NDArray[np.float64]]:
        """
        Returns the 1D arrays representing the x and y axes coordinates
        of the discrete space grid
        """
        return self.x_1d, self.y_1d

    def contains(self, position: CartesianCoordinate) -> bool:
        """
        Checks if a given CartesianCoordinate is within the DSpace bounds.
        """
        x_min, x_max = self.x_1d.min(), self.x_1d.max()
        y_min, y_max = self.y_1d.min(), self.y_1d.max()

        return (x_min <= position.x <= x_max) and (y_min <= position.y <= y_max)

    def distance(self, P1: CartesianCoordinate, P2: CartesianCoordinate) -> float:
        """
        Calculates the Euclidean distance between two Cartesian coordinates P1 and P2
        """
        return np.sqrt((P2.x - P1.x) ** 2 + (P2.y - P1.y) ** 2)


#HELPER

def calculate_bounds_and_params(node_positions, padding=50, dspace_step=1.0) -> int:
    """Compute the DSpace 'npt' parameter required to contain the topology."""
    if not node_positions:
        return 200  # Fallback
    min_x = min(p.x for p in node_positions)
    max_x = max(p.x for p in node_positions)
    min_y = min(p.y for p in node_positions)
    max_y = max(p.y for p in node_positions)
    max_abs_coord = max(
        abs(min_x - padding),
        abs(max_x + padding),
        abs(min_y - padding),
        abs(max_y + padding),
    )
    half_n = int(np.ceil(max_abs_coord / dspace_step)) + 2
    dspace_npt = half_n * 2

    print(
        f"Topology bounds: X=[{min_x:.1f}, {max_x:.1f}], Y=[{min_y:.1f}, {max_y:.1f}]"
    )
    print(
        f"DSpace params: step={dspace_step}, npt={dspace_npt} (Grid span approx. [{-half_n*dspace_step:.1f}, {half_n*dspace_step-dspace_step:.1f}])"
    )
    return dspace_npt
