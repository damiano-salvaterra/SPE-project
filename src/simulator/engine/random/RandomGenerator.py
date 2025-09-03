from simulator.engine.random import RandomManager
import scipy.stats as stats


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
