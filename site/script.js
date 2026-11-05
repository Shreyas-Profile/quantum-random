// Backend API base. Override by setting window.QR_API before loading this script.
const API = window.QR_API || 'https://quantum-api.shreyas.uk';
const WS_API = API.replace(/^http/, 'ws');

// --- Live bit stream via WebSocket ----------------------------------
const streamEl = document.getElementById('bit-stream');
const statusEl = document.getElementById('live-status');
const metaEl = document.getElementById('live-meta');
let streamBuf = '';
const STREAM_MAX_CHARS = 420;

function connectStream() {
  statusEl.textContent = 'connecting…';
  statusEl.classList.remove('off');
  let ws;
  try {
    ws = new WebSocket(`${WS_API}/ws/stream`);
  } catch (e) {
    statusEl.textContent = 'offline';
    statusEl.classList.add('off');
    return;
  }
  ws.onopen = () => {
    statusEl.textContent = 'live • streaming';
    statusEl.classList.remove('off');
  };
  ws.onmessage = (ev) => {
    try {
      const msg = JSON.parse(ev.data);
      if (msg.error) {
        statusEl.textContent = 'bits exhausted';
        statusEl.classList.add('off');
        return;
      }
      streamBuf += String(msg.bit);
      if (streamBuf.length > STREAM_MAX_CHARS) {
        streamBuf = streamBuf.slice(-STREAM_MAX_CHARS);
      }
      streamEl.textContent = streamBuf;
      if (typeof msg.remaining === 'number') {
        metaEl.textContent = `${msg.remaining.toLocaleString()} bits remaining in pool`;
      }
    } catch { /* ignore malformed frames */ }
  };
  ws.onclose = () => {
    statusEl.textContent = 'offline';
    statusEl.classList.add('off');
    setTimeout(connectStream, 3000); // auto-reconnect
  };
  ws.onerror = () => { try { ws.close(); } catch {} };
}
connectStream();

// --- Coin flip ------------------------------------------------------
const coinBtn = document.getElementById('coin-btn');
const coinValue = document.getElementById('coin-value');
coinBtn.addEventListener('click', async () => {
  coinBtn.disabled = true;
  try {
    const r = await fetch(`${API}/api/coin`);
    const d = await r.json();
    if (d.error) {
      coinValue.textContent = '!';
    } else {
      coinValue.textContent = d.face === 'heads' ? 'H' : 'T';
    }
  } catch {
    coinValue.textContent = 'off';
  } finally {
    coinBtn.disabled = false;
  }
});

// --- Dice roll ------------------------------------------------------
const diceBtn = document.getElementById('dice-btn');
const diceValue = document.getElementById('dice-value');
diceBtn.addEventListener('click', async () => {
  diceBtn.disabled = true;
  try {
    const r = await fetch(`${API}/api/dice?sides=6`);
    const d = await r.json();
    if (d.error) {
      diceValue.textContent = '!';
    } else {
      diceValue.textContent = d.roll;
    }
  } catch {
    diceValue.textContent = 'off';
  } finally {
    diceBtn.disabled = false;
  }
});

// --- Download bits --------------------------------------------------
const downloadBtn = document.getElementById('download-btn');
const downloadLink = document.getElementById('download-link');
downloadBtn.addEventListener('click', async () => {
  downloadBtn.disabled = true;
  try {
    const r = await fetch(`${API}/api/bits?n=256`);
    const d = await r.json();
    if (d.error) {
      downloadLink.textContent = 'none left';
      downloadLink.href = '#';
    } else {
      const blob = new Blob([d.bits], { type: 'text/plain' });
      const url = URL.createObjectURL(blob);
      downloadLink.href = url;
      downloadLink.download = `quantum-bits-${Date.now()}.txt`;
      downloadLink.textContent = `${d.n} bits ready`;
      downloadLink.click();
    }
  } catch {
    downloadLink.textContent = 'offline';
  } finally {
    downloadBtn.disabled = false;
  }
});

// --- NIST results ---------------------------------------------------
async function loadNist() {
  const body = document.getElementById('nist-body');
  const meta = document.getElementById('nist-meta');
  try {
    const r = await fetch(`${API}/api/nist`);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const d = await r.json();
    body.innerHTML = d.results.map(x => `
      <tr>
        <td>${x.test}</td>
        <td>${x.p_value.toFixed(4)}</td>
        <td class="${x.passed ? 'result-pass' : 'result-fail'}">${x.passed ? 'PASS' : 'FAIL'}</td>
      </tr>
    `).join('');
    meta.textContent = `${d.passed_count}/${d.total} tests passed on ${d.n_bits.toLocaleString()} certified bits`;
  } catch (e) {
    body.innerHTML = `<tr><td colspan="3" style="color:var(--bad)">Failed to load NIST report: ${e.message}</td></tr>`;
    meta.textContent = '';
  }
}
loadNist();
