"""Bake the clean bits + NIST report into a static JSON bundle the
frontend can consume without a backend. 1 million bits + the NIST
report, dropped at site/data.json."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parent.parent
CLEAN = ROOT / "data" / "clean.bits"
NIST = ROOT / "data" / "nist.json"
OUT = ROOT / "site" / "data.json"

N_BITS_FOR_SITE = 1_000_000


def main() -> int:
    bits = np.unpackbits(np.frombuffer(CLEAN.read_bytes(), dtype=np.uint8))
    bit_str = "".join(str(int(b)) for b in bits[:N_BITS_FOR_SITE])
    nist = json.loads(NIST.read_text())
    bundle = {
        "bits": bit_str,
        "total_bits_certified": int(bits.size),
        "bits_in_bundle": len(bit_str),
        "nist": nist,
        "generated_at": __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        ).isoformat(),
    }
    OUT.write_text(json.dumps(bundle))
    size_mb = OUT.stat().st_size / 1_000_000
    print(f"wrote {OUT} ({size_mb:.2f} MB, {len(bit_str):,} bits + NIST)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
