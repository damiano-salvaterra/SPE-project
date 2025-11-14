import pandas as pd
from typing import TYPE_CHECKING

from simulator.engine.common.Monitor import Monitor
from simulator.entities.applications.common.app_signals import (
    AppProcessStartSignal,
    AppSendSignal,
)

# Avoid circular import issues at type-checking time
if TYPE_CHECKING:
    from simulator.entities.common import Entity, EntitySignal


class InterarrivalTimeMonitor(Monitor):
    """
    Monitor that tracks the interarrival times of packet sent by the application of each node
    """

    def __init__(self, monitor_name: str = "IT", verbose=True):
        super().__init__(monitor_name=monitor_name, verbose=verbose)

        self.arrival_times_map = {} #key: emitting host linkaddr, value: list of arrival times


    def update(self, entity: "Entity", signal: "EntitySignal"):

        if not hasattr(signal, "get_log_data"):
            return

        if not isinstance(signal, (AppSendSignal, AppProcessStartSignal)):
            return  # consider only send signals
        
        
        
        host_addr = entity.host._linkaddr.hex()
        
        if isinstance(signal, AppProcessStartSignal):
            #New app started: put the host in the dict and set reference
            if host_addr not in self.arrival_times_map.keys():
                self.arrival_times_map[host_addr] = []
                self.arrival_times_map[host_addr].append(signal.timestamp)

            if self.verbose:
                    print(
                        f"[IT_MONITOR] [{signal.timestamp:.6f}s] [{entity.host.id}] App Process Started"
                    )

        elif isinstance(signal, AppSendSignal):
            if host_addr not in self.arrival_times_map.keys():
                self.arrival_times_map[host_addr] = [] #create the key if it missed the process start, there is no reference anyways since hte diffs are computed at the end

            self.arrival_times_map[host_addr].append(signal.timestamp)

            if self.verbose:
                print(
                    f"[IT_MONITOR] [{signal.timestamp:.6f}s] [{entity.host.id}] App Send captured with an interarrival time of {(self.arrival_times_map[host_addr][-1]
                                                                                                                                 - self.arrival_times_map[host_addr][-2]):.3f}s"
                )



        
    def save_to_csv(self, base_path: str):
        #convert the dict into a list (of length 1) of dict with key: host, value: mean interarrival time
        log_row = {} #row of the csv: one column for each host. Only one row with the average IT
        for host, at_vec in self.arrival_times_map.items(): #get inter-arrival times
            diffs = []
            for i in range(0, len(at_vec)-1):
                diffs.append(at_vec[i+1]-at_vec[i]) #inter-arrival times vector
            mean_it = sum(diffs)/len(diffs) #compute mean
            log_row[host] = mean_it
        #create list of dict as requested by Monitor base class
        self.log = [log_row]

        super().save_to_csv(base_path)

                