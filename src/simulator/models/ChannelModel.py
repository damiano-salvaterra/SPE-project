import numpy as np
from  numpy.typing import NDArray # static type hints for numpy
from typing import Tuple
'''
This class implement the wireless channel model of attenuation. The model is the classical
path loss + shadowing + fading. The type of fading is configurable, while the shadowing is generated
by generating a random Gaussian field over a 2D discrete square space, and then correlated as the Gudmundson modle of shadowing using a 2D convolution
(i.e using an LTI filter over a gaussian process to generate "colored" noise).
'''

class ChannelModel:

    def __init__(self, freq: float, coh_d: float,
                 shadow_dev : float, dspace_step : int, dspace_npt: int) -> None:
        
        self.freq = freq  # Frequency of the signal in Hz
        self.coh_d = coh_d  # Coherence distance in meters
        self.shadow_dev = shadow_dev  # Standard deviation of shadowing
        self.dspace_step = dspace_step  # Step size in the discrete space
        self.dspace_npt = dspace_npt  # number of points per dimension of discrete the space
        self._size = self.dspace_npt * self.dspace_step

        self.X, self.Y = self._create_dspace_grid() # create discrete space


    def _create_dspace_grid(self) -> Tuple[NDArray[np.float64], NDArray[np.float64]]:
        x = np.linspace(0, self._size, self.dspace_npt) # create x dimension
        y = np.linspace(0, self._size, self.dspace_npt) # create y dimension
        X, Y = np.meshgrid(x,y) # create the grid by cartesian product
                                # X is the matrix of x coordinates, Y the matrix of y coordinates
                                # to access the grid point (i,j)'s space coordinates we need to to do
                                # x = X[i,j] and y = Y[i,j]
        return X, Y
    
    def _LTI_coloring_filter(self, kernel_npt : int = None ) -> NDArray[np.float64]:
        '''
        Generates the frequency response of a 2D LTI filter
        used to color a Gaussian random field. The filter is based on the Gudmundson correlation
        model.
        Kernel_npt is the number of points in the kernel grid. If not provided, it defaults to the number
        of points in the discrete space grid (self.dspace_npt).
        Returns the normalized frequency response of the LTI filter in the frequency domain.
        '''
        if kernel_npt is None:
            kernel_npt = self.dspace_npt
            kernel_size = self._size
        else:
            kernel_size = kernel_npt * self.dspace_step

        half_size = kernel_size/2
        kx = np.linspace(-half_size, +half_size, kernel_npt) # create x dimension
        ky = np.linspace(-half_size, +half_size, kernel_npt) # create y dimension

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


    def generate_shadowing_map(self) -> NDArray[np.float64]:
        # Generate the Gaussian random field

        gaussian_field = np.random.normal(0, self.shadow_dev, (self.dspace_npt, self.dspace_npt)) # TODO: change this and call the Random class instead

        gaussian_field_k = np.fft.fft2(gaussian_field) # Forier transform of the gaussian field

        Hk = self._LTI_coloring_filter() # LTI coloring filter (in frequency domain)
        colored_field_k = gaussian_field_k * Hk # Apply the filter in frequency domain
        
        shadowing_map = np.fft.ifft2(colored_field_k).real # Transform back to the spatial domain
        np.isclose(np.std(shadowing_map), self.shadow_dev, rtol=0.2), "something is wrong in the coloring process"

        return shadowing_map

        


    def _gudmundson_correlation(self, delta : NDArray[np.float64]) -> NDArray[np.float64]:
        '''
        Returns the correlation between two points a and b according to the Gudmundson model
        '''
        corr = (self.shadow_dev**2) * np.exp(-(delta/self.coh_d))
        return corr
    

