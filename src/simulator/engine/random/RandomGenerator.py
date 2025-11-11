from simulator.engine.random import RandomManager
import scipy.stats as stats
from scipy.stats import expon
from typing import Any


class RandomGenerator:
    """
    This class is a wrapper around a random number generator stream managed by the RandomManager to allow
    the generation of antithetic variates.
    """

    def __init__(
        self,
        random_manager: RandomManager,
        stream_key: str,
    ) -> None:
        self._random_manager = random_manager
        self._stream_key = stream_key
        self._antithetic = random_manager.is_antithetic()
        self._random_manager.create_stream(self._stream_key)
        self._stream = self._random_manager.get_stream(self._stream_key)

    def uniform(self, low: float = 0.0, high: float = 1.0, size=None):
        if self._antithetic:
            if size is None:
                return high + low - self._stream.uniform(low, high)
            else:
                return high + low - self._stream.uniform(low, high, size=size)
        else:
            if size is None:
                return self._stream.uniform(low, high)
            else:
                return self._stream.uniform(low, high, size=size)

    def nakagami(self, shape: float, scale: float = 1.0, size=None):
        # Calling the ppf (percent point function) of the Nakagami in combination with a uniform sampling of this class allows to generate antithetic Nakagami samples, since the generated uniform samples are antithetic
        if size is None:
            return stats.nakagami.ppf(self.uniform(), shape, scale=scale)
        else:
            return stats.nakagami.ppf(self.uniform(size=size), shape, scale=scale)

    def normal(self, loc: float = 0.0, scale: float = 1.0, size=None):
        # Calling the ppf (percent point function) of the normal in combination with a uniform sampling of this class allows to generate antithetic normal samples, since the generated uniform samples are antithetic
        if size is None:
            return stats.norm.ppf(self.uniform(), loc, scale)
        else:
            return stats.norm.ppf(self.uniform(size=size), loc, scale)

    def exponential(self, scale: float = 1.0, size=None):
        """
        Generates exponential random variates using the inverse transform method
        to support antithetic variates.

        Args:
            scale (float): The scale parameter (1/lambda), which is the
                           mean of the distribution (e.g., mean_interarrival_time).
            size: The number of variates to generate.
        """
        if size is None:
            return expon.ppf(self.uniform(), scale=scale)
        else:
            return expon.ppf(self.uniform(size=size), scale=scale)

    def integers(self, low: int, high: int) -> int:
        """
        Generates a single random integer in the range [low, high)
        using the inverse transform method to support antithetic variates.

        Args:
            low (int): The lower bound (inclusive).
            high (int): The upper bound (exclusive).

        Returns:
            int: A random integer.
        """
        # Get the number of possible integers
        span = high - low
        if span <= 0:
            return low

        # Use self.uniform() which provides U or (1-U)
        u = self.uniform()

        # Apply inverse transform: floor(U * N)
        # We use int() which acts as floor() for positive numbers
        offset = int(u * span)

        # Clamp the result to be safe in the antithetic edge case
        # where U=0.0 -> (1-U)=1.0, which would result in offset=span
        if offset >= span:
            offset = span - 1

        return low + offset

    def choice(self, a: list) -> Any:
        """
        Selects a single random element from a list, supporting
        antithetic variates by using self.integers().

        Args:
            a (list): The list to choose from.

        Returns:
            Any: A random element from the list.
        """
        if not a:
            return None

        n = len(a)
        index = self.integers(low=0, high=n)
        return a[index]
