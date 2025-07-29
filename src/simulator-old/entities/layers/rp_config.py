# This config file containts all the parameters of the TARP

#


MAX_PATH_LENGTH = 40


''' 
Timers (in seconds)
'''
TREE_BEACON_INTERVAL = 60
SUBTREE_REPORT_OFFSET = TREE_BEACON_INTERVAL / 3
NBR_TBL_CLEANUP_INTERVAL = 15

# NullRDC-version timers

TREE_BEACON_FORWARD_DELAY_base = 0.1
TREE_BEACON_FORWARD_DELAY_jitter_range = 0.125

#this is the base, the actual value is computed in runtime
SUBTREE_REPORT_BASE_DEL_base = 5 # timer for the first subtree report after receiving beacon
                                # HAS TO BE DIVIDED BY THE HOP COUNT
SUBTREE_REPORT_BASE_DEL_jitter_range = 0.04

# the value of this can be computed only in runtime
#SUBTREE_REPORT_NODE_INTERVAL = SUBTREE_REPORT_OFFSET* (1 + (1/hops))

#this is called topology report jitter in the report, and SUBTREE_REPORT_DELAY in the implementation code
TOPOLOGY_REPORT_DELAY_base = 0.1
TOPOLOGY_REPORT_DELAY_jitter_range = 0.1 


'''
Metric parameters
'''

RSSI_HIGH_REF = -35
RSSI_LOW_THR = -85
DELTA_ETX_MIN = 0.3
THR_H = 100
#NullRDC-version
ALPHA = 0.9