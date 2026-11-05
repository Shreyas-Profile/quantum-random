"""Webcam capture → raw bit stream.

Grabs N frames from the default webcam, strips the least-significant
bit of every pixel (and every channel for colour frames), packs them
into bytes and writes to a binary file.

The LSB carries most of the shot-noise information. Higher bits are
dominated by the scene content and sensor gain, which are deterministic.
Pointing the camera at a covered lens or a stable dim scene maximises
the quantum fraction of the signal because shot noise is a larger share
of the total when the raw photon count is low.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import cv2
import numpy as np


def capture_frames(
    n_frames: int,
    camera_index: int = 0,
    warmup_frames: int = 10,
    delay_ms: int = 0,
) -> np.ndarray:
    """Open the webcam, grab `n_frames` frames, return as uint8 array.

    Shape: (n_frames, H, W, C) where C is 3 for a colour sensor or 1 for
    mono. Warmup frames are discarded so auto-exposure can settle.
    """
    cap = cv2.VideoCapture(camera_index, cv2.CAP_ANY)
    if not cap.isOpened():
        raise RuntimeError(
            f"Could not open webcam {camera_index}. On Windows make sure "
            "no other app is using the camera."
        )
    try:
        for _ in range(warmup_frames):
            cap.read()

        frames = []
        for i in range(n_frames):
            ok, frame = cap.read()
            if not ok:
                raise RuntimeError(f"Webcam returned no frame at index {i}")
            frames.append(frame)
            if delay_ms:
                time.sleep(delay_ms / 1000)
        return np.stack(frames, axis=0)
    finally:
        cap.release()


def extract_lsb(frames: np.ndarray) -> np.ndarray:
    """Pull the least-significant bit from every pixel of every frame.

    Returns a flat 1-D uint8 array of 0/1 values, length = frames.size.
    """
    return (frames & 1).astype(np.uint8).ravel()


def pack_bits(bits: np.ndarray) -> bytes:
    """Pack a 0/1 uint8 array into bytes (MSB-first, numpy convention)."""
    # Trim to a multiple of 8 for clean byte boundaries
    trim = (bits.size // 8) * 8
    return np.packbits(bits[:trim]).tobytes()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Capture quantum-sourced random bits from a webcam.")
    p.add_argument("--frames", type=int, default=100, help="Number of frames to capture (default 100).")
    p.add_argument("--camera", type=int, default=0, help="Camera index (default 0).")
    p.add_argument("--warmup", type=int, default=10, help="Warmup frames to discard (default 10).")
    p.add_argument("--delay-ms", type=int, default=0, help="Delay between frames in ms (default 0).")
    p.add_argument("--out", type=Path, required=True, help="Output .bits file path.")
    args = p.parse_args(argv)

    print(f"[capture] opening camera {args.camera} and grabbing {args.frames} frames...")
    t0 = time.time()
    frames = capture_frames(args.frames, args.camera, args.warmup, args.delay_ms)
    print(f"[capture] captured {args.frames} frames of shape {frames.shape[1:]} in {time.time()-t0:.1f}s")

    bits = extract_lsb(frames)
    print(f"[capture] extracted {bits.size:,} LSBs (mean={bits.mean():.4f}, expected ~0.5)")

    packed = pack_bits(bits)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(packed)
    print(f"[capture] wrote {len(packed):,} bytes ({len(packed)*8:,} bits) to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
