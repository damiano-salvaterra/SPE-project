from simulator.engine.common.Event import Event


class MacSendReqEvent(Event):
    pass


class MacACKTimeoutEvent(Event):
    pass


class MacACKSendEvent(Event):
    pass


class MacTrySendNextEvent(Event):
    pass
