from simulator.entities.protocols.net.tarp.tarp_structures import TARPRoute
from typing import Optional


def _etx_est_rssi(rssi: float, rssi_high_ref: float, rssi_low_thr: float) -> float:
    """heuristic for the etx based on rssi"""
    if rssi > rssi_high_ref:
        return 1.0
    if rssi < rssi_low_thr:
        return 10.0
    span = rssi_high_ref - rssi_low_thr
    offset = rssi_high_ref - rssi
    frac = offset / span
    return 1.0 + frac * 9.0


def _valid(current_time: float, route: TARPRoute, entry_expiration_time: float) -> bool:
    return current_time - route.age < entry_expiration_time


def _metric(adv_metric: float, etx: float) -> float:
    return adv_metric + etx


def _metric_improv_thr(cur_metric: float, thr_h: float, delta_etx_min: float) -> float:
    if cur_metric <= 0.0:
        return float("inf")
    thr = thr_h / cur_metric
    return delta_etx_min if thr < delta_etx_min else thr


def _preferred(new_m: float, cur_m: float, thr_h: float, delta_etx_min: float) -> bool:
    thr = _metric_improv_thr(cur_m, thr_h, delta_etx_min)
    return (new_m + thr) < cur_m


def _etx_update(
    num_tx: int,
    num_ack: int,
    o_etx: float,
    rssi: Optional[float],
    alpha: float,
    rssi_high_ref: float,
    rssi_low_thr: float,
) -> float:
    n_etx = 0.0
    if num_ack == 0 or alpha == 1:
        effective_rssi = rssi
        if rssi is None:
            effective_rssi = rssi_low_thr - 1.0
        n_etx = _etx_est_rssi(effective_rssi, rssi_high_ref, rssi_low_thr)
    else:
        # EWMA filtering
        n_etx = num_tx / num_ack
        n_etx = alpha * o_etx + (1 - alpha) * n_etx
    return n_etx
