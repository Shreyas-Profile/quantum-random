# quantum-random

A webcam-based quantum random number generator. The least-significant bits
of each pixel in a camera frame carry real quantum shot noise (photons
arrive at the sensor at random times, governed by quantum mechanics). We
extract those bits, remove sensor bias with a Von Neumann extractor and
a SHA-256 hash whitening pass, and certify the output with the industry
standard [NIST SP 800-22](https://csrc.nist.gov/pubs/sp/800/22/r1/a/final)
randomness test suite.

The resulting bit stream is served live over a websocket at
`quantum.shreyas.uk`, where visitors can flip a quantum coin, roll a
quantum die, or download a batch of certified-random bits for their own
use.

## What this is, honestly

A consumer webcam is not a scientific-grade single-photon detector. The
noise in a webcam frame has two components:

- **Shot noise** (quantum) — the random fluctuation in the number of
  photons arriving at each pixel per frame. This is the source we care
  about; it is fundamentally unpredictable even with perfect knowledge of
  the scene and the camera.
- **Thermal/read noise** (classical) — ordinary electrical noise from the
  silicon sensor, the amplifier, and the ADC. This is not quantum and is
  in principle predictable if you knew enough about the chip's state.

The two are mixed in the raw output. We cannot claim pure quantum
randomness, but we can:

1. Show the raw noise distribution matches Poisson statistics (the
   mathematical signature of shot noise), demonstrating a real quantum
   contribution.
2. Show the processed output passes the NIST SP 800-22 test battery, which
   is the certification bar commercial RNG vendors use.

That is a stronger and more honest claim than most hobby "quantum RNG"
projects on the internet make.

## Pipeline

```
 webcam frames
     │
     ▼
 extract least-significant bit per pixel      capture.py
     │
     ▼
 raw bit stream (biased, correlated)
     │
     ▼
 Von Neumann extractor → de-bias              extractor.py
     │
     ▼
 SHA-256 whitening     → uniform              extractor.py
     │
     ▼
 certified random bits
     │
     ├── NIST SP 800-22 tests                 nist/
     │       └── report JSON
     │
     └── served over websocket                 server.py
             └── website UI                    site/
```

## Running it

```bash
# Install
python -m venv .venv
. .venv/Scripts/activate       # Windows / Git Bash
pip install -r requirements.txt

# Capture 100,000 raw bits from the default webcam
python -m quantum_random.capture --frames 200 --out data/raw.bits

# Clean + whiten to certified bits
python -m quantum_random.extractor --in data/raw.bits --out data/clean.bits

# Run NIST SP 800-22 on the output
python -m quantum_random.nist_runner --in data/clean.bits --report data/nist.json

# Serve bits over websocket + REST
python -m quantum_random.server
```

## Verifying the pipeline without a webcam

The repo ships with a synthetic shot-noise generator so the whole
pipeline can be tested end-to-end before a real camera is plugged in:

```bash
python -m quantum_random.synthetic --frames 200 --out data/raw.bits
```

If the synthetic bits pass NIST after extraction, the pipeline is sound.

## Credits & references

- Shot noise and Poisson statistics — standard quantum optics result; see
  Loudon, "The Quantum Theory of Light" (3rd ed, Oxford, 2000).
- NIST SP 800-22 Rev 1a — Statistical Test Suite for Random and
  Pseudorandom Number Generators.
- Von Neumann extractor — J. von Neumann, "Various Techniques Used in
  Connection with Random Digits", NBS Applied Math Series 12, 1951.
- Commercial QRNGs using the same shot-noise idea at single-photon scale:
  ID Quantique Quantis, PicoQuant.

Built by Shreyas Pavuluri.
