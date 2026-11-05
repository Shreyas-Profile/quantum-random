"""Synthetic shot-noise generator.

Produces fake webcam frames whose per-pixel values follow Poisson
statistics (the mathematical signature of shot noise) plus a small
sensor-electronics bias. Lets the full pipeline be tested end-to-end
without a real camera.

Not a replacement for a real camera; the point is to verify every stage
of the pipeline is correct. If the pipeline cleans this up to pass
NIST, it will also clean up real webcam data.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

from .capture import extract_lsb, pack_bits


def synthetic_frames(
    n_frames: int,
    height: int = 480,
    width: int = 640,
    channels: int = 3,
    mean_photons: float = 30.0,
    sensor_bias: float = 0.52,
    seed: int | None = None,
) -> np.ndarray:
    """Produce synthetic frames that mimic a dim webcam capture.

    Pixel values are Poisson-distributed around `mean_photons` (the raw
    photon count). A small bias is baked into the LSB so the extractor
    has something to clean up — simulating an imperfectly balanced
    sensor. All counts clipped to the 0-255 uint8 range.
    """
    rng = np.random.default_rng(seed)
    shape = (n_frames, height, width, channels)
    # Shot noise component (Poisson around mean_photons)
    shot = rng.poisson(lam=mean_photons, size=shape)
    # Classical noise (gaussian, small)
    classical = rng.normal(loc=0.0, scale=1.2, size=shape)
    raw = shot + classical
    # Inject a tiny LSB bias so the extractor has real work to do
    if sensor_bias != 0.5:
        bias_flip = rng.random(size=shape) < (sensor_bias - 0.5)
        raw = raw + bias_flip.astype(np.int32)
    return np.clip(np.round(raw), 0, 255).astype(np.uint8)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Synthesize shot-noise frames for testing.")
    p.add_argument("--frames", type=int, default=200)
    p.add_argument("--height", type=int, default=480)
    p.add_argument("--width", type=int, default=640)
    p.add_argument("--channels", type=int, default=3)
    p.add_argument("--mean", type=float, default=30.0, help="Mean photon count per pixel (keep low for max shot noise share).")
    p.add_argument("--bias", type=float, default=0.52, help="Target LSB bias (0.5 = perfectly balanced).")
    p.add_argument("--seed", type=int, default=None)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args(argv)

    print(f"[synth] generating {args.frames} frames of shape ({args.height}, {args.width}, {args.channels})...")
    frames = synthetic_frames(
        args.frames, args.height, args.width, args.channels,
        mean_photons=args.mean, sensor_bias=args.bias, seed=args.seed,
    )
    bits = extract_lsb(frames)
    print(f"[synth] produced {bits.size:,} LSBs (mean={bits.mean():.4f})")
    packed = pack_bits(bits)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(packed)
    print(f"[synth] wrote {len(packed):,} bytes to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
