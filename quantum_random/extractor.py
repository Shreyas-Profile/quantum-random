"""Bias extractor + whitening pass.

Raw webcam LSBs are slightly biased (sensor electronics skew the balance
between 0 and 1) and may show weak short-range correlations. This module
turns a biased-and-correlated raw stream into a uniform, independent bit
stream suitable for cryptographic use.

Stages:
  1. Von Neumann extractor — pairs the raw bits and emits only when the
     two bits of a pair differ. (00, 11) → emit nothing; 01 → emit 0;
     10 → emit 1. The output is provably unbiased so long as consecutive
     raw bits are independent of each other, even if each bit is biased.
     In practice it also shrinks the stream by at least 4x (more if bias
     is large).
  2. SHA-256 whitening — the Von Neumann output still has short-range
     correlations from the camera sensor (adjacent pixels share
     amplifier noise, nearby rows share row-read timing). We split the
     extracted stream into 512-bit blocks and hash each block with
     SHA-256, emitting the 256-bit digest. This is standard practice
     for "whitening" a physical entropy source: SHA-256 is modelled as a
     random oracle and compresses any structured 512-bit input to a
     uniform 256-bit output, at the cost of another 2x compression.

Net compression: typically 8-16x from raw LSBs to certified bits.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

import numpy as np


def unpack_bits(data: bytes) -> np.ndarray:
    return np.unpackbits(np.frombuffer(data, dtype=np.uint8))


def pack_bits(bits: np.ndarray) -> bytes:
    trim = (bits.size // 8) * 8
    return np.packbits(bits[:trim]).tobytes()


def von_neumann(bits: np.ndarray) -> np.ndarray:
    """Pair consecutive bits; emit only when they differ."""
    if bits.size < 2:
        return np.array([], dtype=np.uint8)
    # Trim to even length then view as pairs
    n = (bits.size // 2) * 2
    pairs = bits[:n].reshape(-1, 2)
    first, second = pairs[:, 0], pairs[:, 1]
    keep = first != second
    out = first[keep]  # When bits differ, emit the first bit
    return out.astype(np.uint8)


def sha256_whiten(bits: np.ndarray, in_block: int = 512, out_block: int = 256) -> np.ndarray:
    """Hash every `in_block` bits down to `out_block` bits using SHA-256.

    Standard 'hash extractor' construction used for whitening physical
    entropy sources. Effectively compresses 2x with strong statistical
    guarantees under the random-oracle model.
    """
    if out_block > 256:
        raise ValueError("SHA-256 digest is 256 bits; out_block must be <= 256")
    # Pack to bytes block by block
    n_blocks = bits.size // in_block
    if n_blocks == 0:
        return np.array([], dtype=np.uint8)
    output = np.empty(n_blocks * out_block, dtype=np.uint8)
    byte_per_in = in_block // 8
    for i in range(n_blocks):
        block_bits = bits[i * in_block : (i + 1) * in_block]
        block_bytes = np.packbits(block_bits).tobytes()
        # Guard: packbits produces ceil(bits/8) bytes. For 512 bits it is 64.
        assert len(block_bytes) == byte_per_in
        digest = hashlib.sha256(block_bytes).digest()
        digest_bits = np.unpackbits(np.frombuffer(digest, dtype=np.uint8))[:out_block]
        output[i * out_block : (i + 1) * out_block] = digest_bits
    return output


def extract(raw_bits: np.ndarray) -> np.ndarray:
    """Full extractor: Von Neumann then SHA-256 whitening."""
    vn = von_neumann(raw_bits)
    return sha256_whiten(vn)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="De-bias and whiten a raw bit stream.")
    p.add_argument("--in", dest="input", type=Path, required=True, help="Raw bits file.")
    p.add_argument("--out", type=Path, required=True, help="Clean bits output file.")
    args = p.parse_args(argv)

    raw = unpack_bits(args.input.read_bytes())
    print(f"[extractor] loaded {raw.size:,} raw bits (mean={raw.mean():.4f})")

    vn = von_neumann(raw)
    print(f"[extractor] von Neumann: {vn.size:,} bits (compression {raw.size/max(vn.size,1):.1f}x, mean={vn.mean():.4f})")

    clean = sha256_whiten(vn)
    print(f"[extractor] SHA-256 whitened: {clean.size:,} bits (compression {raw.size/max(clean.size,1):.1f}x total, mean={clean.mean():.4f})")

    packed = pack_bits(clean)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(packed)
    print(f"[extractor] wrote {len(packed):,} bytes to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
