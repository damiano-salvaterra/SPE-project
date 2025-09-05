from dataclasses import dataclass
from enum import Enum


class NodeType(Enum):
    NODE_PARENT = 0
    NODE_CHILD = 1
    NODE_DESCENTANT = 2
    NODE_NEIGHBOR = 3


@dataclass
class TARPRoute:  # routing table entry class
    type: NodeType
    age: float
    nexthop: bytes
    hops: int
    etx: float
    num_tx: int
    num_ack: int
    adv_metric: float


class RouteStatus(Enum):
    STATUS_ADD = 1
    STATUS_REMOVE = 0
