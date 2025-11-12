"""
This class manages the random number generation for the simulator.
It uses a Philox RNG and substreams identified by a string key for different parts of the simulation.
It allows also to pass a worker ID in order to ensur unique seeding for each worker, in case of parallel simulations.
"""

from numpy.random import Generator, Philox
from simulator.engine.random.RandomGenerator import RandomGenerator
import hashlib
from typing import Dict


class RandomManager:
    def __init__(
        self, root_seed: int = 0, worker_id=0, antithetic: bool = False
    ) -> None:
        self.antithetic = antithetic
        self._root_seed = root_seed
        self._worker_id = worker_id
        self._worker_seed = [
            worker_id,
            root_seed,
        ]  # to ensure unique seeds for each worker
        self._engines: Dict[str, RandomGenerator] = {}

    def create_stream(self, key: str) -> None:
        key = key.lower()
        if key in self._engines.keys():
            raise ValueError(f"Stream with key '{key}' already exists.")

        key_hash = int.from_bytes(
            hashlib.sha256(key.encode()).digest(), "little"
        )  # get a stable hash for the key
        stream_seed = [
            key_hash
        ] + self._worker_seed  # create a unique seed for the stream
        bitgen = Philox(stream_seed)  # init the new bitgen
        native_stream = Generator(bitgen)  # create new variate generator
        wrapper_rng = RandomGenerator(
                native_stream=native_stream,
                is_antithetic=self.antithetic
            )
        self._engines[key] = wrapper_rng  # add the new stream to the dictionary

    def get_stream(self, key: str) -> RandomGenerator:
        key = key.lower()
        if key not in self._engines.keys():
            raise ValueError(f"Stream with key '{key}' does not exist.")

        return self._engines[key]

    def reset(self, new_root_seed: int = 0) -> None:
        self.__init__(root_seed=new_root_seed, worker_id=self._worker_id, antithetic=self.antithetic)

    def is_antithetic(self) -> bool:
        return self.antithetic
    
