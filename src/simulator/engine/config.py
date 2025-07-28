'''
This file contains some constants and configuration parameters
'''

SCHEDULER_TIME_SCALE = 0.001 # default 1ms for unit time of the scheduler.
                             #When scheduling an event, please  divide the time (in seconds) by this value.
                             #This is to avoid floating point precision issues. (SHOULD BE DONE DIRECTLY IN THE SCHEDULER)
                             # events are created with time in seconds, the scheduler will convert it to the internal time scale.