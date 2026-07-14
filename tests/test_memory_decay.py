"""Unit tests for decay.py — pure functions, no I/O."""

from __future__ import annotations

import math
import pytest
from axiom.memory.decay import (
    compute_R,
    reinforce_stability,
    compute_spreading_boost,
    classify_decay_state,
    STABILITY_BY_TYPE,
)


class TestComputeR:
    def test_at_t0_retrievability_is_one(self):
        assert compute_R(stability=10.0, elapsed_days=0.0) == pytest.approx(1.0)

    def test_at_9S_retrievability_is_e_inverse(self):
        S = 5.0
        R = compute_R(stability=S, elapsed_days=9.0 * S)
        assert R == pytest.approx(math.exp(-1.0), rel=1e-6)

    def test_decay_decreases_with_time(self):
        S = 2.0
        R1 = compute_R(S, 1.0)
        R2 = compute_R(S, 5.0)
        assert R1 > R2

    def test_higher_stability_decays_slower(self):
        elapsed = 5.0
        R_low = compute_R(stability=1.0, elapsed_days=elapsed)
        R_high = compute_R(stability=10.0, elapsed_days=elapsed)
        assert R_high > R_low

    def test_zero_stability_returns_zero(self):
        assert compute_R(stability=0.0, elapsed_days=5.0) == 0.0

    def test_negative_stability_returns_zero(self):
        assert compute_R(stability=-1.0, elapsed_days=5.0) == 0.0

    def test_working_type_s0_fades_fast(self):
        S = STABILITY_BY_TYPE["working"]  # 0.04
        # At S=0.04, R < 0.2 requires t > 0.36*ln(5) ≈ 0.58 days; use 1.0 day
        R = compute_R(S, elapsed_days=1.0)
        assert R < 0.2  # should be nearly forgotten after 1 day

    def test_identity_type_s0_stays_high(self):
        S = STABILITY_BY_TYPE["identity"]  # 365
        R = compute_R(S, elapsed_days=30.0)
        assert R > 0.9  # identity hardly decays over 30 days


class TestReinforceStability:
    def test_low_R_gives_large_boost(self):
        S = 5.0
        new_S = reinforce_stability(S, R=0.1, growth_factor=2.0)
        assert new_S == pytest.approx(S * (1.0 + 2.0 * 0.9))

    def test_high_R_gives_small_boost(self):
        S = 5.0
        new_S = reinforce_stability(S, R=0.9, growth_factor=2.0)
        assert new_S == pytest.approx(S * (1.0 + 2.0 * 0.1))

    def test_low_R_boost_larger_than_high_R(self):
        S = 5.0
        low_R_boost = reinforce_stability(S, R=0.1)
        high_R_boost = reinforce_stability(S, R=0.9)
        assert low_R_boost > high_R_boost

    def test_R_zero_triples_stability_with_default_factor(self):
        # S_new = S × (1 + 2.0 × 1.0) = S × 3.0
        assert reinforce_stability(4.0, R=0.0) == pytest.approx(12.0)

    def test_R_one_gives_minimal_boost(self):
        # S_new = S × (1 + 2.0 × 0.0) = S
        assert reinforce_stability(4.0, R=1.0) == pytest.approx(4.0)

    def test_custom_growth_factor(self):
        S = 2.0
        new_S = reinforce_stability(S, R=0.5, growth_factor=3.0)
        assert new_S == pytest.approx(S * (1.0 + 3.0 * 0.5))


class TestComputeSpreadingBoost:
    def test_1hop_base(self):
        boost = compute_spreading_boost(rel_strength=1.0, depth=1)
        assert boost == pytest.approx(0.3)

    def test_2hop_half_of_1hop(self):
        boost = compute_spreading_boost(rel_strength=1.0, depth=2)
        assert boost == pytest.approx(0.15)

    def test_3hop_quarter_of_1hop(self):
        boost = compute_spreading_boost(rel_strength=1.0, depth=3)
        assert boost == pytest.approx(0.075)

    def test_cap_at_0_5(self):
        # Very high rel_strength should be capped at 0.5
        boost = compute_spreading_boost(rel_strength=100.0, depth=1)
        assert boost == pytest.approx(0.5)

    def test_rel_strength_scales_boost(self):
        boost_half = compute_spreading_boost(rel_strength=0.5, depth=1)
        boost_full = compute_spreading_boost(rel_strength=1.0, depth=1)
        assert boost_half == pytest.approx(boost_full * 0.5)


class TestClassifyDecayState:
    def test_healthy_above_half(self):
        assert classify_decay_state(0.9) == "healthy"
        assert classify_decay_state(0.51) == "healthy"

    def test_fading_between_0_2_and_0_5(self):
        assert classify_decay_state(0.5) == "fading"
        assert classify_decay_state(0.21) == "fading"

    def test_forgotten_at_or_below_0_2(self):
        assert classify_decay_state(0.2) == "forgotten"
        assert classify_decay_state(0.1) == "forgotten"
        assert classify_decay_state(0.0) == "forgotten"
