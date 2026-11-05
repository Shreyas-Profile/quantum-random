"""NIST SP 800-22 Rev 1a statistical test suite — Python implementation.

Implements the eight core tests that commercial RNG vendors use for
basic certification. Each test produces a p-value in [0, 1]; the RNG
passes a test when p-value >= 0.01 (the standard NIST threshold).

Covered tests:
  1. Frequency (monobit)                — §2.1
  2. Frequency within a block           — §2.2
  3. Runs                               — §2.3
  4. Longest run of ones in a block     — §2.4
  5. Discrete Fourier Transform         — §2.6
  6. Serial                             — §2.11
  7. Approximate entropy                — §2.12
  8. Cumulative sums (forward)          — §2.13

Not implemented (these need either very large inputs or external
reference tables; we note them as "not run" rather than falsely pass
them):
  - Binary matrix rank (§2.5)   — needs ~100 000+ bits per block
  - Non-overlapping template matches (§2.7)
  - Overlapping template matches (§2.8)
  - Maurer's universal (§2.9)
  - Linear complexity (§2.10)
  - Random excursions (§2.14) + variants (§2.15)

Reference:
  NIST SP 800-22 Rev 1a, "A Statistical Test Suite for Random and
  Pseudorandom Number Generators for Cryptographic Applications."
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy.special import erfc, gammaincc


PASS_THRESHOLD = 0.01  # NIST standard


@dataclass
class TestResult:
    name: str
    p_value: float
    passed: bool
    details: dict


# ----------------------------------------------------------------------
# §2.1  Frequency (monobit) test
# ----------------------------------------------------------------------

def frequency_monobit(bits: np.ndarray) -> TestResult:
    """Tests whether the proportion of 0s and 1s in the whole sequence
    is close to 0.5, as it would be for a random sequence."""
    n = bits.size
    s = int(2 * bits.sum() - n)  # +1 for a 1, -1 for a 0, summed
    s_obs = abs(s) / math.sqrt(n)
    p = erfc(s_obs / math.sqrt(2))
    return TestResult(
        "Frequency (monobit)",
        float(p),
        p >= PASS_THRESHOLD,
        {"n": n, "sum_pm1": s},
    )


# ----------------------------------------------------------------------
# §2.2  Frequency within a block
# ----------------------------------------------------------------------

def frequency_block(bits: np.ndarray, block_size: int = 128) -> TestResult:
    """Tests whether the proportion of 1s within each M-bit block is
    close to 0.5, catching sequences that are balanced globally but
    unbalanced locally."""
    n = bits.size
    n_blocks = n // block_size
    if n_blocks < 1:
        return TestResult(
            "Frequency within a block", float("nan"), False,
            {"error": "not enough bits", "need": block_size, "have": n},
        )
    trimmed = bits[: n_blocks * block_size].reshape(n_blocks, block_size)
    pi = trimmed.mean(axis=1)
    chi_sq = 4 * block_size * ((pi - 0.5) ** 2).sum()
    p = gammaincc(n_blocks / 2, chi_sq / 2)
    return TestResult(
        "Frequency within a block",
        float(p),
        p >= PASS_THRESHOLD,
        {"n": n, "block_size": block_size, "n_blocks": int(n_blocks), "chi_sq": float(chi_sq)},
    )


# ----------------------------------------------------------------------
# §2.3  Runs test
# ----------------------------------------------------------------------

def runs(bits: np.ndarray) -> TestResult:
    """Tests the total number of runs (uninterrupted sequences of
    identical bits). Non-random sequences oscillate too much or too
    little."""
    n = bits.size
    pi = bits.mean()
    # Prerequisite from the NIST spec: |pi - 0.5| < 2/sqrt(n)
    if abs(pi - 0.5) >= 2 / math.sqrt(n):
        return TestResult(
            "Runs", 0.0, False,
            {"error": "monobit prerequisite failed", "pi": float(pi)},
        )
    v_n = int(1 + np.sum(bits[:-1] != bits[1:]))
    numerator = abs(v_n - 2 * n * pi * (1 - pi))
    denominator = 2 * math.sqrt(2 * n) * pi * (1 - pi)
    p = erfc(numerator / denominator)
    return TestResult(
        "Runs",
        float(p),
        p >= PASS_THRESHOLD,
        {"n": n, "runs": v_n, "pi": float(pi)},
    )


# ----------------------------------------------------------------------
# §2.4  Longest run of ones in a block
# ----------------------------------------------------------------------

_LONGEST_RUN_PARAMS = {
    # block size M → (K, N, categories, pi_i probabilities)
    8:    (3, 16,   [1, 2, 3, 4],
           [0.2148, 0.3672, 0.2305, 0.1875]),
    128:  (5, 49,   [4, 5, 6, 7, 8, 9],
           [0.1174, 0.2430, 0.2493, 0.1752, 0.1027, 0.1124]),
    10000:(6, 75,   [10, 11, 12, 13, 14, 15, 16],
           [0.0882, 0.2092, 0.2483, 0.1933, 0.1208, 0.0675, 0.0727]),
}


def longest_run_of_ones(bits: np.ndarray) -> TestResult:
    n = bits.size
    # Pick block size based on input length per the NIST spec
    if n >= 1_000_000:
        M = 10_000
    elif n >= 6_272:
        M = 128
    elif n >= 128:
        M = 8
    else:
        return TestResult(
            "Longest run of ones", float("nan"), False,
            {"error": "not enough bits", "need": 128, "have": n},
        )
    K, N, cats, pi_i = _LONGEST_RUN_PARAMS[M]
    blocks = bits[: N * M].reshape(N, M)
    # Find the longest run of 1s in each block
    def longest(row):
        max_r = cur = 0
        for b in row:
            cur = cur + 1 if b else 0
            if cur > max_r:
                max_r = cur
        return max_r
    runs_ = np.apply_along_axis(longest, 1, blocks)
    # Bucket counts: runs <= cats[0] in bucket 0, runs == cats[i] in bucket i, runs >= cats[-1] in last bucket
    v = np.zeros(len(cats), dtype=int)
    for r in runs_:
        if r <= cats[0]:
            v[0] += 1
        elif r >= cats[-1]:
            v[-1] += 1
        else:
            v[cats.index(r)] += 1
    chi_sq = float(np.sum((v - N * np.array(pi_i)) ** 2 / (N * np.array(pi_i))))
    p = gammaincc(K / 2, chi_sq / 2)
    return TestResult(
        "Longest run of ones in a block",
        float(p),
        p >= PASS_THRESHOLD,
        {"n": n, "M": M, "N": N, "counts": v.tolist(), "chi_sq": chi_sq},
    )


# ----------------------------------------------------------------------
# §2.6  Discrete Fourier Transform (spectral) test
# ----------------------------------------------------------------------

def dft_spectral(bits: np.ndarray) -> TestResult:
    """Looks for periodic patterns in the sequence by taking a DFT and
    checking how many peaks exceed the 95% threshold expected for a
    random sequence."""
    n = bits.size
    if n < 1000:
        return TestResult(
            "DFT (spectral)", float("nan"), False,
            {"error": "need at least 1000 bits", "have": n},
        )
    x = 2 * bits.astype(np.int8) - 1  # map 0->-1, 1->+1
    s = np.fft.fft(x)
    modulus = np.abs(s[: n // 2])
    T = math.sqrt(math.log(1 / 0.05) * n)
    N0 = 0.95 * n / 2
    N1 = int((modulus < T).sum())
    d = (N1 - N0) / math.sqrt(n * 0.95 * 0.05 / 4)
    p = erfc(abs(d) / math.sqrt(2))
    return TestResult(
        "DFT (spectral)",
        float(p),
        p >= PASS_THRESHOLD,
        {"n": n, "N0_expected": float(N0), "N1_observed": N1, "T": float(T)},
    )


# ----------------------------------------------------------------------
# §2.11  Serial test (m = 3)
# ----------------------------------------------------------------------

def _psi_sq(bits: np.ndarray, m: int) -> float:
    if m == 0:
        return 0.0
    n = bits.size
    # Append first m-1 bits to end for circular handling
    ext = np.concatenate([bits, bits[: m - 1]]) if m > 1 else bits
    # Convert m-bit windows to integers
    vals = np.zeros(ext.size - m + 1, dtype=np.int64)
    for i in range(m):
        vals = (vals << 1) | ext[i : ext.size - m + 1 + i]
    counts = np.bincount(vals, minlength=1 << m)
    return float((2 ** m / n) * np.sum(counts ** 2) - n)


def serial(bits: np.ndarray, m: int = 3) -> TestResult:
    """Tests the frequency of every m-bit overlapping pattern. Random
    sequences have roughly uniform pattern frequencies."""
    n = bits.size
    if n < 2 ** m * 16:
        return TestResult(
            "Serial", float("nan"), False,
            {"error": "not enough bits", "need": 2 ** m * 16, "have": n},
        )
    psi_m = _psi_sq(bits, m)
    psi_m1 = _psi_sq(bits, m - 1)
    psi_m2 = _psi_sq(bits, m - 2)
    del1 = psi_m - psi_m1
    del2 = psi_m - 2 * psi_m1 + psi_m2
    p1 = gammaincc(2 ** (m - 2), del1 / 2)
    p2 = gammaincc(2 ** (m - 3), del2 / 2)
    passed = (p1 >= PASS_THRESHOLD) and (p2 >= PASS_THRESHOLD)
    return TestResult(
        "Serial",
        float(min(p1, p2)),
        passed,
        {"n": n, "m": m, "p_value_1": float(p1), "p_value_2": float(p2)},
    )


# ----------------------------------------------------------------------
# §2.12  Approximate entropy
# ----------------------------------------------------------------------

def approximate_entropy(bits: np.ndarray, m: int = 2) -> TestResult:
    n = bits.size
    if n < 1000:
        return TestResult(
            "Approximate entropy", float("nan"), False,
            {"error": "need at least 1000 bits", "have": n},
        )

    def phi(block_len: int) -> float:
        ext = np.concatenate([bits, bits[: block_len - 1]]) if block_len > 1 else bits.copy()
        windows = np.zeros(n, dtype=np.int64)
        for i in range(block_len):
            windows = (windows << 1) | ext[i : i + n]
        counts = np.bincount(windows, minlength=1 << block_len)
        p = counts[counts > 0] / n
        return float(np.sum(p * np.log(p)))

    ap_en = phi(m) - phi(m + 1)
    chi_sq = 2 * n * (math.log(2) - ap_en)
    p = gammaincc(2 ** (m - 1), chi_sq / 2)
    return TestResult(
        "Approximate entropy",
        float(p),
        p >= PASS_THRESHOLD,
        {"n": n, "m": m, "ApEn": float(ap_en), "chi_sq": float(chi_sq)},
    )


# ----------------------------------------------------------------------
# §2.13  Cumulative sums (forward)
# ----------------------------------------------------------------------

def cumulative_sums(bits: np.ndarray) -> TestResult:
    n = bits.size
    if n < 100:
        return TestResult(
            "Cumulative sums", float("nan"), False,
            {"error": "need at least 100 bits", "have": n},
        )
    x = 2 * bits.astype(np.int32) - 1
    z = int(np.max(np.abs(np.cumsum(x))))

    from scipy.stats import norm

    def phi(y):
        return norm.cdf(y)

    k_range1 = range(int((-n / z + 1) // 4), int((n / z - 1) // 4) + 1)
    k_range2 = range(int((-n / z - 3) // 4), int((n / z - 1) // 4) + 1)
    sum1 = sum(phi(((4 * k + 1) * z) / math.sqrt(n)) - phi(((4 * k - 1) * z) / math.sqrt(n)) for k in k_range1)
    sum2 = sum(phi(((4 * k + 3) * z) / math.sqrt(n)) - phi(((4 * k + 1) * z) / math.sqrt(n)) for k in k_range2)
    p = 1.0 - sum1 + sum2
    p = max(0.0, min(1.0, float(p)))
    return TestResult(
        "Cumulative sums (forward)",
        p,
        p >= PASS_THRESHOLD,
        {"n": n, "max_abs_cusum": z},
    )


# ----------------------------------------------------------------------
# Orchestrator
# ----------------------------------------------------------------------

ALL_TESTS = [
    frequency_monobit,
    frequency_block,
    runs,
    longest_run_of_ones,
    dft_spectral,
    serial,
    approximate_entropy,
    cumulative_sums,
]


def run_all(bits: np.ndarray) -> list[TestResult]:
    return [t(bits) for t in ALL_TESTS]


def unpack_bits(data: bytes) -> np.ndarray:
    return np.unpackbits(np.frombuffer(data, dtype=np.uint8))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Run NIST SP 800-22 tests on a bit stream.")
    p.add_argument("--in", dest="input", type=Path, required=True)
    p.add_argument("--report", type=Path, required=True)
    args = p.parse_args(argv)

    bits = unpack_bits(args.input.read_bytes())
    print(f"[nist] loaded {bits.size:,} bits")
    results = run_all(bits)
    report = {
        "n_bits": int(bits.size),
        "threshold": PASS_THRESHOLD,
        "results": [
            {"test": r.name, "p_value": float(r.p_value), "passed": bool(r.passed), "details": r.details}
            for r in results
        ],
        "passed_count": int(sum(1 for r in results if r.passed)),
        "total": len(results),
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2))
    print(f"[nist] wrote {args.report}")
    for r in results:
        flag = "PASS" if r.passed else "FAIL"
        print(f"  [{flag}] {r.name:40s}  p={r.p_value:.4f}")
    print(f"[nist] summary: {report['passed_count']}/{report['total']} tests passed")
    return 0 if report["passed_count"] == report["total"] else 1


if __name__ == "__main__":
    sys.exit(main())
