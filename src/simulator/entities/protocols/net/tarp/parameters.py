from dataclasses import dataclass


@dataclass
class TARPParameters:
    MAX_STAT_PER_FRAGMENT = 37  # Max bytes allowed per packet (PHY) in 802.15.4 is 127.
    # Approximately, taking out all the overhead due to header (TARP included), we are left with around 112 bytes
    # now, each status voice in the report is 3 bytes, plus une byte for the number of voices. so we can send maximum 37
    # voices in the topology report. However, Contiki often keep the packetbuf smaller than 127 bytes. So we may want to set an arbitrary value
    MAX_PATH_LENGTH = 40  # maximum number of hops before dropping the packet
    CLEANUP_INTERVAL = (
        15  # cleanup the routing table from expired entries every 15 seconds
    )
    ALWAYS_VALID_AGE = float("inf")
    ALWAYS_INVALID_AGE = -1  # time 0. Route having this age are always invalid.
    # In the C implementation it has value zero, but in the DES the time 0 actually exists so we need a smaller value
    ENTRY_EXPIRATION_TIME = 90 
    TREE_BEACON_INTERVAL = 60
    SUBTREE_REPORT_OFFEST = TREE_BEACON_INTERVAL / 3

    SUBTREE_REPORT_DELAY: float = 0.1
    SUBTREE_REPORT_MAX_JITTER = 0.1
  
    INITIAL_REPORT_MAX_JITTER : float = 0.4
    INITIAL_REPORT_BASE_DELAY: float = 5.0 # Base delay for the depth-staggered initial report (T_R_first = 5/hops + jitter)

    RSSI_LOW_THR = -85
    RSSI_HIGH_REF = -35
    DELTA_ETX_MIN = 0.3

    # NullRDC mode constants  and delays
    THR_H = 50
    ALPHA = 0.5
    TREE_BEACON_FORWARD_MAX_JITTER = 1 / 8
    TREE_BEACON_FORWARD_BASE_DELAY = 0.1
