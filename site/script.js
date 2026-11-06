// Static-only: fetch the pre-generated bit bundle + NIST report from
// site/data.json. The "live" stream is a visual effect consuming the
// bundle at ~20 bits/sec, with a running cursor wrapping around.

let DATA = null;
let streamCursor = 0;
const STREAM_INTERVAL_MS = 50;      // one bit every 50ms
const STREAM_MAX_CHARS = 420;

const streamEl = document.getElementById('bit-stream');
const statusEl = document.getElementById('live-status');
const metaEl = document.getElementById('live-meta');
const coinBtn = document.getElementById('coin-btn');
const coinValue = document.getElementById('coin-value');
const diceBtn = document.getElementById('dice-btn');
const diceValue = document.getElementById('dice-value');
const downloadBtn = document.getElementById('download-btn');
const downloadLink = document.getElementById('download-link');

async function load() {
  statusEl.textContent = 'loading…';
  try {
    const r = await fetch('data.json', { cache: 'no-cache' });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    DATA = await r.json();
    statusEl.textContent = 'playing • certified random';
    statusEl.classList.remove('off');
    startStream();
    renderNist();
  } catch (e) {
    statusEl.textContent = `offline: ${e.message}`;
    statusEl.classList.add('off');
  }
}

function startStream() {
  let buf = '';
  setInterval(() => {
    if (!DATA) return;
    const total = DATA.bits.length;
    const bit = DATA.bits[streamCursor % total];
    streamCursor = (streamCursor + 1) % total;
    buf += bit;
    if (buf.length > STREAM_MAX_CHARS) buf = buf.slice(-STREAM_MAX_CHARS);
    streamEl.textContent = buf;
    metaEl.textContent = `position ${streamCursor.toLocaleString()} of ${total.toLocaleString()} • ${DATA.total_bits_certified.toLocaleString()} total certified bits`;
  }, STREAM_INTERVAL_MS);
}

function takeBits(n) {
  // Pull n bits from a random spot in the bundle (so successive clicks
  // don't correlate with the stream cursor).
  if (!DATA) return null;
  const start = Math.floor(Math.random() * (DATA.bits.length - n));
  return DATA.bits.slice(start, start + n);
}

coinBtn?.addEventListener('click', () => {
  const b = takeBits(1);
  if (!b) { coinValue.textContent = '!'; return; }
  coinValue.textContent = b === '1' ? 'H' : 'T';
});

diceBtn?.addEventListener('click', () => {
  // Rejection sample until we land in [0, 6)
  for (let i = 0; i < 128; i++) {
    const b = takeBits(3);
    if (!b) { diceValue.textContent = '!'; return; }
    const v = parseInt(b, 2);
    if (v < 6) { diceValue.textContent = v + 1; return; }
  }
  diceValue.textContent = '!';
});

downloadBtn?.addEventListener('click', () => {
  const b = takeBits(256);
  if (!b) { downloadLink.textContent = 'offline'; return; }
  const blob = new Blob([b], { type: 'text/plain' });
  const url = URL.createObjectURL(blob);
  downloadLink.href = url;
  downloadLink.download = `quantum-bits-${Date.now()}.txt`;
  downloadLink.textContent = '256 bits ready';
  downloadLink.click();
});

function renderNist() {
  const body = document.getElementById('nist-body');
  const meta = document.getElementById('nist-meta');
  const n = DATA?.nist;
  if (!n) {
    body.innerHTML = '<tr><td colspan="3">No NIST report</td></tr>';
    return;
  }
  body.innerHTML = n.results.map(x => `
    <tr>
      <td>${x.test}</td>
      <td>${x.p_value.toFixed(4)}</td>
      <td class="${x.passed ? 'result-pass' : 'result-fail'}">${x.passed ? 'PASS' : 'FAIL'}</td>
    </tr>
  `).join('');
  meta.textContent = `${n.passed_count}/${n.total} tests passed on ${n.n_bits.toLocaleString()} certified bits`;
}

load();
