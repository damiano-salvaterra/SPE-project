import numpy as np
from  numpy.typing import NDArray # static type hints for numpy
from scipy.interpolate import RegularGridInterpolator
import scipy.constants as const
from scipy.stats import nakagami
from typing import Tuple

from . import topology as tp
'''
This class implement the wireless channel model of attenuation. The model is the classical
path loss + shadowing + fading. The type of fading is configurable, while the shadowing is generated
by generating a random Gaussian field over a 2D discrete square space, and then correlated as the Gudmundson modle of shadowing using a 2D convolution
(i.e using an LTI filter over a gaussian process to generate "colored" noise).
'''

class ChannelModel:

    def __init__(self, rng: np.random.Generator, dspace: tp.DSpace, freq: float, coh_d: float,
                 shadow_dev: float, pl_exponent: float, d0: float, fading_shape: float) -> None:
    
        self._rng = rng  # Random number generator
        self.freq = freq  # Frequency of the signal in Hz
        self.coh_d = coh_d  # Coherence distance in meters
        self.shadow_dev = shadow_dev  # Standard deviation of shadowing
        self.pl_exponent = pl_exponent # Path loss exponent
        self.d0 = d0 # Reference distance for log path loss
        self.fading_shape = fading_shape  # Nakagami fading shape parameter
        #self.fading_scale = fading_scale  # Nakagami fading scale parameter
        self.dspace = dspace
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
        gaussian_field = self._rng.normal(0, self.shadow_dev, (self.dspace.npt, self.dspace.npt))
        gaussian_field_k = np.fft.fft2(gaussian_field) # Fourier transform of the gaussian field

        Hk = self._LTI_coloring_filter(kernel_npt) # LTI coloring filter (in frequency domain)
        colored_field_k = gaussian_field_k * Hk # Apply the filter in frequency domain
        
        shadowing_map = np.fft.ifft2(colored_field_k).real # Transform back to the spatial domain
        np.isclose(np.std(shadowing_map), self.shadow_dev, rtol=0.2), "something is wrong in the coloring process"

        self.shadowing_map = shadowing_map

    


    def _shadowing_power_on_point(self, P: tp.CartesianCoordinate) -> np.float64:
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
    
    

    def _link_shadowing_loss(self, A: tp.CartesianCoordinate, B: tp.CartesianCoordinate) -> np.float64:
        '''
        Returns the shadowing loss along the link A<->B. A and B are real-world cartesian coordinates
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



    def _path_loss(self, A: tp.CartesianCoordinate, B: tp.CartesianCoordinate, Pt_dBm : np.float64 = 0 ) -> np.float64:
        '''
        Returns the path loss in dB between two points A and B using a simplified log-distance model.
        Pt_dBm is the transitted power in dBm.
        Reference to: Andrea Goldsmith, Wireless Communications, Sec. 2.6 - 2005
        '''
        d = self.dspace.distance(A, B)
        if d < self.d0:
            d = self.d0  # if distance is less than reference distance, clamp to d0 (otherwise we have negative path loss)

        lambda_ =  const.c / self.freq
        ref_fspl = 20* np.log10(lambda_ / (4*const.pi * self.d0)) # free space path loss (Friis eq.) as constant reference
        Pr_dBm = Pt_dBm + ref_fspl - 10 * self.pl_exponent * np.log10(d / self.d0)

        return Pr_dBm
    

    
    def total_link_loss(self, A: tp.CartesianCoordinate, B: tp.CartesianCoordinate, Pt_dBm: np.float64 = 0) -> np.float64:
        '''
        Returns the total loss (shadowing + path loss + fading) between two points A and B.
        Pt_dBm is the transmitted power in dBm.
        '''
        shadowing_loss = self._link_shadowing_loss(A, B)
        path_loss = self._path_loss(A, B, Pt_dBm)
        avg_recv_power_linear = 10 ** ((path_loss + shadowing_loss) / 10)
        #self.fading_scale = np.sqrt(avg_recv_power_linear)
        fading_loss = nakagami.rvs(self.fading_shape, scale=avg_recv_power_linear, random_state = self._rng)  # Nakagami fading: gives the amplitude variation
                                                                                    # need to square it to have the power. TODO: check this

        total_loss = shadowing_loss + path_loss + 20 * np.log10(fading_loss)
        return total_loss


    def total_loss_from_point(self, A: tp.CartesianCoordinate, Pt_dBm: np.float64 = 0) -> NDArray[np.float64]:
        '''
        Compute a 2D map of total loss in dB from the given coordinate to every point on the grid.
        Returns an array of shape (dspace.npt, dspace.npt).
        EXPENSIVE FUNCTION, USE ONLY FOR DEBUG
        '''
        n = self.dspace.npt
        loss_map = np.zeros((n, n), dtype=np.float64)
        for i in range(n):
            for j in range(n):
                P = self.dspace.to_cartesian_coordinates(i, j)
                loss_map[i, j] = self.total_link_loss(A, P, Pt_dBm)
        return loss_map
