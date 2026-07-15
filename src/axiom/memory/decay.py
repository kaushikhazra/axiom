import math

STABILITY_BY_TYPE = {
    "working": 0.04,
    "episodic": 2.0,
    "semantic": 14.0,
    "procedural": 60.0,
    "identity": 365.0,
    "person": 90.0,
}


def compute_R(stability: float, elapsed_days: float) -> float:
    """R(t) = e^(−t / (9 · S))"""
    if stability <= 0:
        return 0.0
    return math.exp(-elapsed_days / (9.0 * stability))


def reinforce_stability(S: float, R: float, growth_factor: float = 2.0) -> float:
    """S_new = S × (1 + growth_factor × (1 − R))"""
    return S * (1.0 + growth_factor * (1.0 - R))


def compute_spreading_boost(rel_strength: float, depth: int) -> float:
    """1-hop = 0.3 × rel_strength; each hop × 0.5; cap 0.5"""
    boost = 0.3 * rel_strength * (0.5 ** (depth - 1))
    return min(boost, 0.5)


def classify_decay_state(R: float) -> str:
    if R > 0.5:
        return "healthy"
    elif R > 0.2:
        return "fading"
    else:
        return "forgotten"
