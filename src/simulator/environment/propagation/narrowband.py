import numpy as np
from numpy.typing import NDArray  # static type hints for numpy
from scipy.interpolate import RegularGridInterpolator
import scipy.constants as const

from simulator.environment.geometry import CartesianCoordinate, DSpace
from simulator.engine.random import RandomManager, RandomGenerator

"""
This class implement the wireless channel model of attenuation. The model is the classical
path loss + shadowing + fading. The type of fading is configurable, while the shadowing is generated
by generating a random Gaussian field over a 2D discrete square space, and then correlated as the Gudmundson modle of shadowing using a 2D convolution
(i.e using an LTI filter over a gaussian process to generate "colored" noise).
"""


class NarrowbandChannelModel:

    def __init__(
        self,
        random_manager: RandomManager,
        dspace: DSpace,
        freq: float,
        filter_bandwidth: float,
        coh_d: float,
        shadow_dev: float,
        pl_exponent: float,
        d0: float,
        fading_shape: float,
    ) -> None:
        self._shadowing_rng = RandomGenerator(
            random_manager, "NBMODEL/SHADOWING"
        )  # Random number generator for the shadowing
        self._fading_rng = RandomGenerator(
            random_manager, "NBMODEL/FADING"
        )  # random number generator for fading (to be totally precise we should create a fading rng for each link/node)
        self.freq = freq  # Frequency of the signal in Hz
        self.filter_bandwitdh = filter_bandwidth  # radio passband filter bandwidth (nominal IEEE 802.15.4 BW: 5 Mhz, actual RF filter BW for DSSS O-QPSK: around 2MHZ) # TODO: check this
        self.coh_d = coh_d  # Coherence distance in meters
        self.shadow_dev = shadow_dev  # Standard deviation of shadowing
        self.pl_exponent = pl_exponent  # Path loss exponent
        self.d0 = d0  # Reference distance for log path loss
        self.fading_shape = fading_shape  # Nakagami fading shape parameter
        self.dspace = dspace  # Discrete space grid
        self.shadowing_map = None

    def _gudmundson_correlation(
        self, delta: NDArray[np.float64]
    ) -> NDArray[np.float64]:
        """
        Returns the correlation between two points a and b according to the Gudmundson model
        """
        corr = (self.shadow_dev**2) * np.exp(-(delta / self.coh_d))
        return corr

    def _LTI_coloring_filter(self, kernel_npt: int = None) -> NDArray[np.float64]:
        """
        Generates the frequency response of a 2D LTI filter
        used to color a Gaussian random field. The filter is based on the Gudmundson correlation
        model.
        Kernel_npt is the number of points in the kernel grid. If not provided, it defaults to the number
        of points in the discrete space grid.
        Returns the normalized frequency response of the LTI filter in the frequency domain.
        """
        if kernel_npt is None:
            kernel_npt = self.dspace.npt

        half_k = kernel_npt // 2
        kx = self.dspace.step * np.arange(-half_k, kernel_npt - half_k)
        ky = self.dspace.step * np.arange(-half_k, kernel_npt - half_k)

        if kernel_npt < self.dspace.npt:  # zero pad to reach the same size as the space
            pad_size = (self.dspace.npt - kernel_npt) // 2
            kx = np.pad(kx, (pad_size, pad_size), mode="constant", constant_values=0)
            ky = np.pad(ky, (pad_size, pad_size), mode="constant", constant_values=0)

        KX, KY = np.meshgrid(kx, ky)  # create kernel grid

        D = np.sqrt(KX**2 + KY**2)  # radius matrix from the origin of the filter
        R = self._gudmundson_correlation(D)  # correlation matrix
        R_shift = np.fft.ifftshift(R)
        PSD_k = np.fft.fft2(R_shift)  # power spectral density of the filter
        Hk = np.sqrt(PSD_k)  # obtain the frequency response

        # normalize filter to conserve the enrgy of the colored process
        Ek = np.vdot(Hk, Hk)  # get filter energy (Hermitian dot product)
        Hk_norm = Hk * (
            kernel_npt / np.sqrt(Ek)
        )  # parselval's Theorem (normalization in frequency domain)

        return Hk_norm

    def generate_shadowing_map(self, kernel_npt: int = None) -> None:
        """
        Create the shadowing map. kernel_npt defines the number of points of the correlation kernel
        """
        if kernel_npt is not None:
            assert kernel_npt % 2 == 0, "number of kernel points must be multiple of 2"
        # Generate the Gaussian random field
        gaussian_field = self._shadowing_rng.normal(
            0, self.shadow_dev, (self.dspace.npt, self.dspace.npt)
        )
        gaussian_field_k = np.fft.fft2(
            gaussian_field
        )  # Fourier transform of the gaussian field

        Hk = self._LTI_coloring_filter(
            kernel_npt
        )  # LTI coloring filter (in frequency domain)
        colored_field_k = gaussian_field_k * Hk  # Apply the filter in frequency domain

        shadowing_map = np.fft.ifft2(
            colored_field_k
        ).real  # Transform back to the spatial domain
        np.isclose(
            np.std(shadowing_map), self.shadow_dev, rtol=0.2
        ), "something is wrong in the coloring process"

        self.shadowing_map = shadowing_map

    def _shadowing_power_on_point(self, P: CartesianCoordinate) -> np.float64:
        """
        Returns the shadowing value at the given coordinates (x, y).
        The coordinates (x, y) are real-world coordinates, not grid indices.
        Interpolates the value instead of returning the nearest grid point value.
        """
        assert (
            self.shadowing_map is not None
        ), "Shadowing map has not been generated yet."

        x_axis, y_axis = self.dspace.get_axes_1d()
        interpolator = RegularGridInterpolator(
            (y_axis, x_axis),  # numpy coordinate convention
            self.shadowing_map,
            bounds_error=False,
            fill_value=None,
        )

        value = interpolator([[P.y, P.x]])[
            0
        ]  # returns array of shape (1,), get the scalar
        # by convention coordinates are reversed
        return np.float64(value)

    def _path_loss_dB(self, A: CartesianCoordinate, B: CartesianCoordinate) -> float:
        """
        Returns the path loss in dB between two points A and B using a simplified log-distance model.
        Reference to: Andrea Goldsmith, Wireless Communications, Sec. 2.6 - 2005
        """
        d = self.dspace.distance(A, B)
        if d < self.d0:
            d = self.d0

        lambda_ = const.c / self.freq

        # Free space path loss at d0
        fspl_d0_dB = 20 * np.log10(4 * np.pi * self.d0 / lambda_)

        # log-distance path loss
        path_loss = fspl_d0_dB + 10 * self.pl_exponent * np.log10(d / self.d0)

        return path_loss  # positive path loss value in dB

    def _link_shadowing_loss_dB(
        self, A: CartesianCoordinate, B: CartesianCoordinate
    ) -> np.float64:
        """
        Returns the shadowing loss along the link A<->B. A and B are real-world cartesian coordinates
        Reference to S. Lu, J. May, R.J. Haines, "Efficient Modeling of Correlated Shadow Fading in Dense Wireless Multi-Hop Networks", IEEE WCNC 2014
        """
        sh_A = self._shadowing_power_on_point(A)
        sh_B = self._shadowing_power_on_point(B)

        d_AB = self.dspace.distance(A, B)

        # compute link shadowing loss formula
        shad_ext = sh_A + sh_B  # Sum of shadowing values on the link extremes

        exp_term = np.exp(-(d_AB / self.coh_d))
        num = 1 - exp_term
        den = np.sqrt(2 * (1 + exp_term))

        shad_AB = (num / den) * shad_ext

        return shad_AB

    def total_loss_dB(self, A: CartesianCoordinate, B: CartesianCoordinate) -> float:
        """
        Compute total (positive) loss (for the average power, ie path loss + shadowing) in dB between two points A and B.
        """
        path_loss = self._path_loss_dB(A, B)
        shadowing_loss = self._link_shadowing_loss_dB(A, B)

        total_loss = path_loss + shadowing_loss

        return total_loss

    def link_budget(
        self, A: CartesianCoordinate, B: CartesianCoordinate, Pt_dBm: float
    ) -> float:
        """
        Compute received power in dBm between two points A and B given a transmitted power Pt_dBm.
        Add the fading term with a Nakagami distribution with mean equal to the average received power
        """
        total_loss_dB = self.total_loss_dB(A, B)

        Pr_avg_dBm = Pt_dBm - total_loss_dB
        Pr_avg_linear = 10 ** (Pr_avg_dBm / 10)  # get linear Pr for fading parameter
        fading_amplitude = self._fading_rng.nakagami(
            self.fading_shape, scale=np.sqrt(Pr_avg_linear)
        )

        Pr_instant = fading_amplitude**2
        Pr_instant_dBm = 10 * np.log10(Pr_instant)
        return Pr_instant_dBm

    def noise_floor_deterministic(
        self, noise_temp_K: float = 290
    ) -> float:  # TODO: check this
        """
        Compute the noise floor in dBm for a given noise temperature.
        Default noise temperature is 290 K (room temperature).
        """
        k = const.Boltzmann
        noise_power_W = k * noise_temp_K * self.filter_bandwitdh  # Noise power in Watts
        noise_power_dBm = 10 * np.log10(noise_power_W * 1000)  # Convert to dBm
        return noise_power_dBm

    def propagation_delay(
        self, A: CartesianCoordinate, B: CartesianCoordinate, velocity: float = None
    ) -> float:
        """
        Returns the propagation delay between points A and B.
        velocity: speed of propagation in m/s (defaults to speed of light)
        """
        d = self.dspace.distance(A, B)

        if velocity is None:
            velocity = const.c
        return d / velocity  # seconds

    def dBm_to_watts(self, p_dBm: float) -> float:
        return 10 ** ((p_dBm - 30.0) / 10.0)
