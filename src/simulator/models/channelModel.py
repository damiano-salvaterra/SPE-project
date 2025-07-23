import numpy as np
from  numpy.typing import NDArray # static type hints for numpy
from scipy.interpolate import RegularGridInterpolator
import scipy.constants as const
from scipy.stats import nakagami
from typing import Tuple


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
This class implement the wireless channel model of attenuation. The model is the classical
path loss + shadowing + fading. The type of fading is configurable, while the shadowing is generated
by generating a random Gaussian field over a 2D discrete square space, and then correlated as the Gudmundson modle of shadowing using a 2D convolution
(i.e using an LTI filter over a gaussian process to generate "colored" noise).
'''
class ChannelModel:

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


        #def find_nearest_grid_index(self, P: CartesianCoordinate) -> Tuple[int, int]:
        #    '''
        #    Returns the indices of the nearest grid point
        #    on the shadowing map. P is a tuple containing the (x,y) real-world coordinates
        #    '''
        #    # Convert real-world coordinates to grid indices
        #    x = P.x
        #    y = P.y
        #    i = round((y + self._size / 2) / self.step)
        #    j = round((x + self._size / 2) / self.step)
    
        #    # Ensure indices are within bounds
        #    i = np.clip(i, 0, self.npt - 1)
        #    j = np.clip(j, 0, self.npt - 1)
    
        #    return i, j


        #def to_cartesian_coordinates(self, i: int, j: int) -> CartesianCoordinate:
        #    '''
        #    Given grid indices (i, j), returns the corresponding real-world Cartesian coordinates (x, y)
        #    '''
        #    # Ensure indices are within bounds
        #    i = np.clip(i, 0, self.npt - 1)
        #    j = np.clip(j, 0, self.npt - 1)
    
        #    # Convert grid indices to real-world coordinates
        #    x = j * self.step - self._size / 2
        #    y = i * self.step - self._size / 2
    
        #    return CartesianCoordinate(x,y)


        def distance(self, P1: CartesianCoordinate, P2: CartesianCoordinate) -> float:
            '''
            Calculates the Euclidean distance between two Cartesian coordinates P1 and P2
            '''
            return np.sqrt((P2.x - P1.x) ** 2 + (P2.y - P1.y) ** 2)
        
        
    def __init__(self, shadowing_rng: np.random.Generator, dspace_step: int, dspace_npt: int, freq: float, coh_d: float,
                 shadow_dev: float, pl_exponent: float, d0: float, fading_shape: float) -> None:
    
        
        self._shadowing_rng = shadowing_rng  # Random number generator for the shadowing
        self.freq = freq  # Frequency of the signal in Hz
        self.coh_d = coh_d  # Coherence distance in meters
        self.shadow_dev = shadow_dev  # Standard deviation of shadowing
        self.pl_exponent = pl_exponent # Path loss exponent
        self.d0 = d0 # Reference distance for log path loss
        self.fading_shape = fading_shape  # Nakagami fading shape parameter
        self.dspace = self.DSpace(dspace_step, dspace_npt)  # Discrete space grid
        self.shadowing_map = None





    def _gudmundson_correlation(self, delta : NDArray[np.float64]) -> NDArray[np.float64]:
        '''
        Returns the correlation between two points a and b according to the Gudmundson model
        '''
        corr = (self.shadow_dev**2) * np.exp(-(delta/self.coh_d))
        return corr

    def _LTI_coloring_filter(self, kernel_npt : int = None ) -> NDArray[np.float64]:
        '''
        Generates the frequency response of a 2D LTI filter
        used to color a Gaussian random field. The filter is based on the Gudmundson correlation
        model.
        Kernel_npt is the number of points in the kernel grid. If not provided, it defaults to the number
        of points in the discrete space grid.
        Returns the normalized frequency response of the LTI filter in the frequency domain.
        '''
        if kernel_npt is None:
            kernel_npt = self.dspace.npt

        half_k = kernel_npt // 2
        kx = self.dspace.step * np.arange(-half_k, kernel_npt - half_k)
        ky = self.dspace.step * np.arange(-half_k, kernel_npt - half_k)


        if kernel_npt < self.dspace.npt: # zero pad to reach the same size as the space 
            pad_size = (self.dspace.npt - kernel_npt) // 2
            kx = np.pad(kx, (pad_size, pad_size), mode='constant', constant_values=0)
            ky = np.pad(ky, (pad_size, pad_size), mode='constant', constant_values=0)

        KX, KY = np.meshgrid(kx, ky) # create kernel grid

        D = np.sqrt(KX**2 + KY**2) # radius matrix from the origin of the filter
        R = self._gudmundson_correlation(D) # correlation matrix
        R_shift = np.fft.ifftshift(R)
        PSD_k = np.fft.fft2(R_shift) # power spectral density of the filter
        Hk = np.sqrt(PSD_k) # obtain the frequency response 

        #normalize filter to conserve the enrgy of the colored process
        Ek = np.vdot(Hk, Hk) # get filter energy (Hermitian dot product)
        Hk_norm = Hk * (kernel_npt / np.sqrt(Ek)) # parselval's Theorem (normalization in frequency domain)

        return Hk_norm


    def generate_shadowing_map(self, kernel_npt : int = None) -> None:
        '''
        Create the shadowing map. kernel_npt defines the number of points of the correlation kernel'''
        if kernel_npt is not None:
            assert kernel_npt % 2 == 0, "number of kernel points must be multiple of 2"
        # Generate the Gaussian random field
        gaussian_field = self._shadowing_rng.normal(0, self.shadow_dev, (self.dspace.npt, self.dspace.npt))
        gaussian_field_k = np.fft.fft2(gaussian_field) # Fourier transform of the gaussian field

        Hk = self._LTI_coloring_filter(kernel_npt) # LTI coloring filter (in frequency domain)
        colored_field_k = gaussian_field_k * Hk # Apply the filter in frequency domain
        
        shadowing_map = np.fft.ifft2(colored_field_k).real # Transform back to the spatial domain
        np.isclose(np.std(shadowing_map), self.shadow_dev, rtol=0.2), "something is wrong in the coloring process"

        self.shadowing_map = shadowing_map

    


    def _shadowing_power_on_point(self, P: CartesianCoordinate) -> np.float64:
        '''
        Returns the shadowing value at the given coordinates (x, y).
        The coordinates (x, y) are real-world coordinates, not grid indices.
        Interpolates the value instead of returning the nearest grid point value.
        '''
        assert self.shadowing_map is not None, "Shadowing map has not been generated yet."

        x_axis, y_axis = self.dspace.get_axes_1d()
        interpolator = RegularGridInterpolator(
                        (y_axis, x_axis),      # numpy coordinate convention
                        self.shadowing_map,
                        bounds_error=False,
                        fill_value=None
                        )
    
        value = interpolator([[P.y, P.x]])[0] # returns array of shape (1,), get the scalar
                                          #by convention coordinates are reversed
        return np.float64(value)
    
    


    def _path_loss_dB(self, A: CartesianCoordinate, B: CartesianCoordinate) -> float:
        '''
        Returns the path loss in dB between two points A and B using a simplified log-distance model.
        Reference to: Andrea Goldsmith, Wireless Communications, Sec. 2.6 - 2005
        '''
        d = self.dspace.distance(A, B)
        if d < self.d0:
            d = self.d0
        
        lambda_ = const.c / self.freq
        
        # Free space path loss at d0
        fspl_d0_dB = 20 * np.log10(4 * np.pi * self.d0 / lambda_)
        
        # log-distance path loss
        path_loss = fspl_d0_dB + 10 * self.pl_exponent * np.log10(d / self.d0)
        
        return path_loss  # positive path loss value in dB


    def _link_shadowing_loss_dB(self, A: CartesianCoordinate, B: CartesianCoordinate) -> np.float64:
        '''
        Returns the shadowing loss along the link A<->B. A and B are real-world cartesian coordinates
        Reference to S. Lu, J. May, R.J. Haines, "Efficient Modeling of Correlated Shadow Fading in Dense Wireless Multi-Hop Networks", IEEE WCNC 2014
        '''
        sh_A = self._shadowing_power_on_point(A)
        sh_B = self._shadowing_power_on_point(B)

        d_AB = self.dspace.distance(A, B)

        #compute link shadowing loss formula
        shad_ext = sh_A + sh_B # Sum of shadowing values on the link extremes

        exp_term = np.exp(- (d_AB/self.coh_d))
        num = 1 - exp_term
        den = np.sqrt(2 * (1 + exp_term))

        shad_AB = (num / den) * shad_ext

        return shad_AB




    def total_loss_dB(self, A: CartesianCoordinate, B: CartesianCoordinate) -> float:
        '''
        Compute total (positive) loss (for the average power, ie path loss + shadowing) in dB between two points A and B.
        '''
        path_loss = self._path_loss_dB(A, B)
        shadowing_loss = self._link_shadowing_loss_dB(A, B)

        total_loss = path_loss + shadowing_loss
    
        return total_loss



    def link_budget(self, A: CartesianCoordinate, B: CartesianCoordinate, Pt_dBm: float, link_rng: np.random.Generator) -> float:
        '''
        Compute receive power in dBm between two points A and B given a transmitted power Pt_dBm.
        Add the fading term with a Nakagami distribution with mean equal to the average received power
        '''
        total_loss_dB = self.total_loss_dB(A, B)

        Pr_avg_dBm = Pt_dBm - total_loss_dB
        Pr_avg_linear = 10**(Pr_avg_dBm/10) # get linear Pr for fading parameter
        fading_amplitude = nakagami.rvs(self.fading_shape, scale=np.sqrt(Pr_avg_linear), random_state=link_rng) # TODO: use a different rng for each link. Manage the link's rng in the Topology class

        Pr_instant = fading_amplitude**2
        Pr_instant_dBm = 10*np.log10(Pr_instant)
        return Pr_instant_dBm

