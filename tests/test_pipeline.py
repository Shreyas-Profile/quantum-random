"""End-to-end pipeline smoke test using synthetic shot-noise data."""

from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np

from quantum_random.capture import extract_lsb, pack_bits
from quantum_random.extractor import extract, unpack_bits
from quantum_random.nist import run_all
from quantum_random.synthetic import synthetic_frames


def test_synthetic_pipeline_passes_nist():
    """Synthetic shot noise, run through the full pipeline, must pass
    every implemented NIST test. If this fails the pipeline is broken."""
    frames = synthetic_frames(n_frames=30, seed=42)
    raw_bits = extract_lsb(frames)
    clean_bits = extract(raw_bits)
    assert clean_bits.size > 100_000, "not enough bits for meaningful NIST tests"
    results = run_all(clean_bits)
    failed = [r for r in results if not r.passed]
    assert not failed, f"NIST tests failed: {[(r.name, r.p_value) for r in failed]}"


def test_pack_unpack_roundtrip():
    bits = np.random.default_rng(0).integers(0, 2, size=1000, dtype=np.uint8)
    packed = pack_bits(bits)
    unpacked = unpack_bits(packed)
    assert np.array_equal(unpacked[:1000 - (1000 % 8)], bits[:1000 - (1000 % 8)])
