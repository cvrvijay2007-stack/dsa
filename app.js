// Prim's MST visualizer — frontend.
// The graph is edited locally; the backend computes the algorithm trace,
// generates/parses graphs and persists saved graphs.
'use strict';

const W = 800, H = 500, MAX_NODES = 200;
const $ = (id) => document.getElementById(id);
const svg = $('svg');
const layer = $('layer');

const state = {
  nodes: [],          // {x, y, label?}
  edges: [],          // {a, b, w}
  sel: null,          // selected node index while connecting
  drag: null,
  trace: null,        // PrimTrace from the API, for the current graph + start node
  cursor: -1,         // index into trace.steps; -1 = not started
  fresh: { n: null, e: null }, // node/edge to animate on this render
  timer: null,
  version: 0,         // bumps on every structural change; stale traces are dropped
  pending: null,      // in-flight trace request
  saved: { id: null, name: '' },
  dirty: false,
  algo: 'prim',       // 'prim' | 'kruskal'
};

const ALGO = {
  prim: {
    desc: 'Start at one node. Keep taking the cheapest edge that reaches a node outside the tree, until every node is connected.',
    queueTitle: 'Frontier edges',
    queueDesc: 'Every edge with one end in the tree and one end outside, cheapest first.',
    idleQueue: 'Shown while the algorithm is choosing an edge.',
    pickLegend: 'Cheapest, chosen next',
    phase: { start: 'Starting', frontier: 'Choosing the cheapest edge', add: 'Edge added', done: 'Finished' },
  },
  kruskal: {
    desc: 'Check every edge from cheapest to most expensive. Keep it unless it would close a cycle, until every node is connected.',
    queueTitle: 'Edge queue',
    queueDesc: 'Edges not checked yet, cheapest first. The top one is checked next.',
    idleQueue: 'Shown once the edges are sorted.',
    pickLegend: 'Edge being checked',
    phase: { start: 'Sorting edges', consider: 'Checking the next edge', add: 'Edge kept', skip: 'Edge skipped', done: 'Finished' },
  },
};
const QUEUE_ROWS = 8;
try { if (localStorage.getItem('algo') === 'kruskal') state.algo = 'kruskal'; } catch (e) {}

// ---------- helpers ----------
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const nm = (i) => (state.nodes[i] && state.nodes[i].label) || String.fromCharCode(65 + (i % 26)) + (i >= 26 ? Math.floor(i / 26) : '');
const frame = () => (state.trace && state.cursor >= 0 ? state.trace.steps[state.cursor] : null);
const plural = (n, word) => `${n} ${word}${n === 1 ? '' : 's'}`;

async function api(path, opts = {}) {
  let res;
  try {
    res = await fetch(path, {
      headers: { 'Content-Type': 'application/json' },
      ...opts,
      body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
    });
  } catch {
    setApi(false);
    throw new Error("Can't reach the server. Check that it's running, then try again.");
  }
  setApi(true);
  if (res.status === 204) return null;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const d = data.detail;
    const msg = Array.isArray(d) ? d.map((x) => x.msg.replace(/^Value error, /, '')).join('; ') : d || `Server error (${res.status}). Try again.`;
    throw new Error(msg);
  }
  return data;
}

let toastTimer;
function toast(msg, kind = 'ok') {
  const t = $('toast');
  t.textContent = msg;
  t.className = `toast ${kind}`;
  t.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { t.hidden = true; }, kind === 'err' ? 4500 : 2600);
}

function setApi(ok) {
  const p = $('api');
  p.className = `api-pill ${ok ? 'ok' : 'down'}`;
  p.querySelector('span').textContent = ok ? 'Server connected' : 'Server offline';
}

function graphPayload() {
  return {
    nodes: state.nodes.map((n, i) => ({ x: Math.round(n.x * 10) / 10, y: Math.round(n.y * 10) / 10, label: nm(i) })),
    edges: state.edges.map(({ a, b, w }) => ({ a, b, w })),
  };
}

// ---------- rendering ----------
function render() {
  const f = frame();
  const inT = new Set(f ? f.in_tree : []);
  const mst = new Set(f ? f.mst : []);
  const prim = state.algo === 'prim';
  const cand = new Set(f && prim ? f.candidates : []);
  const skipped = new Set(f ? f.skipped : []);
  const start = +$('start').value || 0;
  let h = '';
  state.edges.forEach((e, i) => {
    const a = state.nodes[e.a], b = state.nodes[e.b];
    let c = '';
    if (f) {
      if (mst.has(i)) c = 'mst';
      else if (f.pick === i) c = 'pick';
      else if (cand.has(i)) c = 'cand';
      else if (skipped.has(i) || (prim && inT.has(e.a) && inT.has(e.b))) c = 'ign';
    }
    const dr = state.fresh.e === i ? ' draw' : '';
    const mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2;
    const bw = Math.max(28, String(e.w).length * 8 + 14);
    const on = c === 'mst' || c === 'pick' ? ' on' : '';
    h += `<g data-e="${i}" class="edge" aria-label="Edge ${esc(nm(e.a))} to ${esc(nm(e.b))}, weight ${e.w}">` +
      `<line class="edge-hit" x1="${a.x}" y1="${a.y}" x2="${b.x}" y2="${b.y}" stroke="transparent" stroke-width="16"/>` +
      `<line class="eline ${c}${dr}" pathLength="1" x1="${a.x}" y1="${a.y}" x2="${b.x}" y2="${b.y}"/>` +
      `<rect class="wbg ${c}" x="${mx - bw / 2}" y="${my - 11}" width="${bw}" height="22" rx="11"/>` +
      `<text class="wt${on}" x="${mx}" y="${my}">${e.w}</text></g>`;
  });
  state.nodes.forEach((n, i) => {
    const cl = ['node'];
    if (inT.has(i)) cl.push('in');
    if (state.sel === i) cl.push('sel');
    if (state.fresh.n === i) cl.push('new');
    if (prim && i === start && !f) cl.push('start');
    const label = nm(i);
    const shown = label.length > 6 ? label.slice(0, 5) + '…' : label;
    const fs = shown.length > 3 ? Math.max(9, 17 - shown.length * 1.4) : 14;
    h += `<g class="${cl.join(' ')}" data-n="${i}" aria-label="Node ${esc(label)}">` +
      `<circle class="ring" cx="${n.x}" cy="${n.y}" r="27"/>` +
      `<circle class="nc" cx="${n.x}" cy="${n.y}" r="20"/>` +
      `<text class="nt" x="${n.x}" y="${n.y}" style="font-size:${fs}px">${esc(shown)}</text></g>`;
  });
  layer.innerHTML = h;
  $('empty').hidden = state.nodes.length > 0;
  renderPanel(f);
}

function renderPanel(f) {
  const n = state.nodes.length;
  const A = ALGO[state.algo];
  // narration
  const phase = $('phase');
  let kind = f ? f.kind : 'idle';
  if (f && f.done) kind = 'done';
  if (f && f.done && state.trace && !state.trace.connected) kind = 'warn';
  phase.dataset.kind = kind;
  phase.textContent = f ? (kind === 'warn' ? 'Stopped early' : A.phase[f.done ? 'done' : f.kind]) : (n ? 'Ready' : 'No graph yet');
  $('status').textContent = f ? f.message
    : n ? `${plural(n, 'node')}, ${plural(state.edges.length, 'edge')}. Press play or step to begin` + (state.algo === 'prim' ? ` from ${nm(+$('start').value || 0)}.` : '.')
    : 'Build or load a graph, then press play.';
  $('tot').textContent = f ? f.total : 0;
  if (state.algo === 'prim') {
    $('joined-label').textContent = 'Nodes joined';
    $('joined').textContent = `${f ? f.in_tree.length : 0}/${n}`;
  } else {
    // Each kept edge merges two trees of the forest.
    $('joined-label').textContent = 'Trees left';
    $('joined').textContent = String(n - (f ? f.mst.length : 0));
  }
  $('kept').textContent = f ? f.mst.length : 0;

  // frontier (Prim) or sorted edge queue (Kruskal) as weight bars
  $('queue-title').textContent = A.queueTitle;
  $('queue-desc').textContent = A.queueDesc;
  const tb = $('tb');
  const showBars = f && f.candidates.length && (state.algo === 'kruskal' || f.kind === 'frontier');
  if (showBars) {
    const max = Math.max(...state.edges.map((e) => e.w));
    const sorted = [...f.candidates].sort((x, y) => state.edges[x].w - state.edges[y].w || x - y);
    const rows = sorted.slice(0, QUEUE_ROWS).map((i) => {
      const e = state.edges[i];
      return `<li class="${i === f.pick ? 'pick' : ''}" data-edge="${i}"><span class="who">${esc(nm(e.a))}–${esc(nm(e.b))}</span>` +
        `<span class="track"><span class="fill" style="width:${Math.max(6, (e.w / max) * 100)}%"></span></span><span class="w">${e.w}</span></li>`;
    });
    if (sorted.length > QUEUE_ROWS) rows.push(`<li><span class="more">and ${sorted.length - QUEUE_ROWS} more</span></li>`);
    tb.innerHTML = rows.join('');
  } else {
    const why = !f ? A.idleQueue : f.done ? 'None left.' : 'Updating after the last edge joined.';
    tb.innerHTML = `<li><span class="none">${why}</span></li>`;
  }

  // step timeline
  const log = $('log');
  if (state.trace && state.trace.steps.length) {
    log.innerHTML = state.trace.steps.slice(0, state.cursor + 1).map((s, i) =>
      `<li data-step="${i}" class="${i === state.cursor ? 'now' : ''}">${esc(s.log)}</li>`).join('') ||
      '<li class="none">Steps appear here as the tree grows.</li>';
  } else {
    log.innerHTML = '<li class="none">Steps appear here as the tree grows.</li>';
  }
  // Keep the current step visible inside the list without scrolling the page.
  const now = log.querySelector('.now');
  if (now) {
    const top = now.offsetTop - log.offsetTop;
    if (top < log.scrollTop) log.scrollTop = top;
    else if (top + now.offsetHeight > log.scrollTop + log.clientHeight) log.scrollTop = top + now.offsetHeight - log.clientHeight;
  }

  // transport
  const total = state.trace ? state.trace.steps.length : 0;
  const sc = $('scrub');
  sc.max = String(Math.max(0, total));
  sc.value = String(state.cursor + 1);
  sc.disabled = !total;
  $('prog').textContent = total ? `Step ${state.cursor + 1} of ${total}` : '';
  $('back').disabled = state.cursor < 0;
  $('step').disabled = !n || (state.trace && state.cursor >= total - 1);
  $('play').disabled = !n;

  // saved status
  const d = $('dirty');
  d.textContent = state.saved.id ? (state.dirty ? `“${state.saved.name}” has unsaved changes.` : `Editing “${state.saved.name}”.`) : '';
  d.className = state.dirty && state.saved.id ? 'text-[13px] mb-2 unsaved' : 'text-[13px] mb-2 text-muted';
}

// ---------- graph lifecycle ----------
function fillStart() {
  const s = $('start'), v = s.value;
  s.innerHTML = state.nodes.map((_, i) => `<option value="${i}">${esc(nm(i))}</option>`).join('');
  if (v !== '' && +v < state.nodes.length) s.value = v;
  s.disabled = !state.nodes.length;
}

function syncText() {
  const used = new Set();
  const lines = state.edges.map((e) => { used.add(e.a); used.add(e.b); return `${nm(e.a)} ${nm(e.b)} ${e.w}`; });
  state.nodes.forEach((_, i) => { if (!used.has(i)) lines.push(nm(i)); });
  $('el').value = lines.join('\n');
}

function stop() {
  clearTimeout(state.timer);
  state.timer = null;
  const p = $('play');
  p.classList.remove('playing');
  p.setAttribute('aria-label', 'Play');
}

/** Rewind to before the first step; keeps the computed trace. */
function rewind() {
  stop();
  state.cursor = -1;
  state.fresh = { n: null, e: null };
  render();
}

/** Graph or start node changed: drop the trace and recompute it in the background. */
function invalidate() {
  state.version++;
  state.trace = null;
  state.pending = null;
  rewind();
  prefetch();
}

function changed() {
  state.dirty = true;
  fillStart();
  syncText();
  invalidate();
}

function setGraph(g, saved = { id: null, name: '' }) {
  state.nodes = g.nodes.map((n) => ({ x: n.x, y: n.y, label: n.label || undefined }));
  state.edges = g.edges.map(({ a, b, w }) => ({ a, b, w }));
  state.sel = null;
  $('start').value = '0';
  changed();
  state.saved = saved;
  state.dirty = false;
  renderSavedMarks();
  render();
}

// ---------- trace ----------
let prefetchTimer;
function prefetch() {
  clearTimeout(prefetchTimer);
  if (!state.nodes.length) return;
  prefetchTimer = setTimeout(() => ensureTrace(true), 120);
}

async function ensureTrace(quiet = false) {
  if (state.trace) return true;
  if (!state.nodes.length) return false;
  const v = state.version;
  if (!state.pending) {
    state.pending = api('/api/mst', { method: 'POST', body: { ...graphPayload(), algorithm: state.algo, start: +$('start').value || 0 } });
  }
  const p = state.pending;
  try {
    const t = await p;
    if (v !== state.version) return false; // graph changed while waiting
    if (!state.trace) { state.trace = t; render(); }
    return true;
  } catch (err) {
    if (state.pending === p) state.pending = null;
    if (!quiet) toast(err.message, 'err');
    return false;
  }
}

function goTo(i) {
  const prev = state.cursor;
  state.cursor = Math.max(-1, Math.min(i, state.trace.steps.length - 1));
  const f = frame();
  state.fresh = f && f.kind === 'add' && state.cursor === prev + 1 ? { n: f.new_node, e: f.new_edge } : { n: null, e: null };
  render();
}

/** Advance one step. Resolves true while more steps remain. */
async function stepForward() {
  if (!(await ensureTrace())) return false;
  const last = state.trace.steps.length - 1;
  if (state.cursor >= last) return false;
  goTo(state.cursor + 1);
  return state.cursor < last;
}

function stepBack() {
  if (!state.trace || state.cursor < 0) return;
  goTo(state.cursor - 1);
}

const delay = () => 2100 - $('spd').value * 190;

async function togglePlay() {
  if (state.timer) { stop(); return; }
  if (!state.nodes.length) return;
  if (state.trace && state.cursor >= state.trace.steps.length - 1) rewind();
  const p = $('play');
  p.classList.add('playing');
  p.setAttribute('aria-label', 'Pause');
  const tick = async () => {
    if (!state.timer) return;
    if (!(await stepForward()) || !state.timer) { stop(); return; }
    state.timer = setTimeout(tick, delay());
  };
  state.timer = setTimeout(tick, 50);
}

$('step').onclick = () => { stop(); stepForward(); };
$('back').onclick = () => { stop(); stepBack(); };
$('reset').onclick = rewind;
$('play').onclick = togglePlay;
$('start').onchange = () => { invalidate(); };
$('scrub').oninput = (ev) => { stop(); if (state.trace) goTo(+ev.target.value - 1); };
$('log').onclick = (ev) => {
  const li = ev.target.closest('[data-step]');
  if (li && state.trace) { stop(); goTo(+li.dataset.step); }
};

document.addEventListener('keydown', (ev) => {
  if (ev.target.closest('input, textarea, select, dialog, [contenteditable]') || ev.metaKey || ev.ctrlKey || ev.altKey) return;
  // Tabs and the algorithm switch use arrow keys for their own navigation.
  if (ev.key.startsWith('Arrow') && ev.target.closest('[role=tab], [role=radio]')) return;
  if (ev.key === ' ') {
    if (ev.target.closest('button, [role=tab]')) return; // native activation handles it
    ev.preventDefault(); togglePlay();
  }
  else if (ev.key === 'ArrowRight') { ev.preventDefault(); stop(); stepForward(); }
  else if (ev.key === 'ArrowLeft') { ev.preventDefault(); stop(); stepBack(); }
  else if (ev.key === 'r' || ev.key === 'R') { rewind(); }
  else if (ev.key === 'Escape' && state.sel !== null) { state.sel = null; render(); }
});

// ---------- canvas editing ----------
function pt(ev) {
  const r = svg.getBoundingClientRect();
  return {
    x: Math.max(24, Math.min(W - 24, ((ev.clientX - r.left) * W) / r.width)),
    y: Math.max(24, Math.min(H - 24, ((ev.clientY - r.top) * H) / r.height)),
  };
}

function addEdge(a, b, w) {
  if (a === b || state.edges.some((e) => (e.a === a && e.b === b) || (e.a === b && e.b === a))) return false;
  const typed = Math.round(+$('w').value);
  state.edges.push({ a, b, w: w || (typed > 0 && typed <= 9999 ? typed : 1 + Math.floor(Math.random() * 20)) });
  return true;
}

function editWeight(i) {
  const e = state.edges[i], a = state.nodes[e.a], b = state.nodes[e.b], inp = $('we');
  inp.style.left = ((a.x + b.x) / 2 / W) * 100 + '%';
  inp.style.top = ((a.y + b.y) / 2 / H) * 100 + '%';
  inp.value = e.w;
  inp.hidden = false;
  const done = (ok) => {
    if (inp.hidden) return;
    inp.hidden = true;
    const v = Math.round(parseFloat(inp.value));
    if (!ok || v === e.w) return;
    if (!(v > 0 && v <= 9999)) { toast('Weights must be whole numbers from 1 to 9999.', 'err'); return; }
    e.w = v;
    changed();
  };
  inp.onkeydown = (k) => { if (k.key === 'Enter') done(true); if (k.key === 'Escape') done(false); };
  inp.onblur = () => done(true);
  setTimeout(() => { inp.focus(); inp.select(); }, 0);
}

let last = { t: 0, k: null };
function isDouble(k) {
  const now = Date.now(), d = last.k === k && now - last.t < 400;
  last = { t: now, k: d ? null : k };
  return d;
}

function deleteNode(k) {
  state.nodes.splice(k, 1);
  state.edges = state.edges
    .filter((e) => e.a !== k && e.b !== k)
    .map((e) => ({ a: e.a > k ? e.a - 1 : e.a, b: e.b > k ? e.b - 1 : e.b, w: e.w }));
  state.sel = null;
  changed();
}

svg.addEventListener('pointerdown', (ev) => {
  if (ev.button !== 0) return;
  const ng = ev.target.closest('[data-n]'), eg = ev.target.closest('[data-e]');
  if (ng) {
    state.drag = { id: +ng.dataset.n, sx: ev.clientX, sy: ev.clientY, moved: false };
    svg.setPointerCapture(ev.pointerId);
    return;
  }
  if (eg) {
    const i = +eg.dataset.e;
    if (ev.target.classList.contains('wbg')) { editWeight(i); return; }
    if (isDouble('e' + i)) { state.edges.splice(i, 1); changed(); }
    return;
  }
  if (state.sel !== null) { state.sel = null; render(); return; }
  if (state.nodes.length >= MAX_NODES) { toast(`A graph can have up to ${MAX_NODES} nodes.`, 'err'); return; }
  state.nodes.push(pt(ev));
  changed();
});

svg.addEventListener('pointermove', (ev) => {
  const d = state.drag;
  if (!d) return;
  if (!d.moved && Math.hypot(ev.clientX - d.sx, ev.clientY - d.sy) < 6) return;
  d.moved = true;
  Object.assign(state.nodes[d.id], pt(ev));
  state.dirty = true;
  state.fresh = { n: null, e: null };
  render();
});

svg.addEventListener('pointerup', () => {
  const d = state.drag;
  if (!d) return;
  state.drag = null;
  if (d.moved) return;
  if (isDouble('n' + d.id)) { deleteNode(d.id); return; }
  if (state.sel === null) state.sel = d.id;
  else if (state.sel === d.id) state.sel = null;
  else {
    const a = state.sel;
    state.sel = null;
    if (addEdge(a, d.id)) { changed(); return; }
    toast(`${nm(a)} and ${nm(d.id)} are already connected.`, 'err');
  }
  render();
});

// ---------- toolbar ----------
$('clr').onclick = () => { setGraph({ nodes: [], edges: [] }); };

$('samp').onclick = async () => {
  try { setGraph(await api('/api/generate/sample')); } catch (e) { toast(e.message, 'err'); }
};

$('rand').onclick = async () => {
  const n = Math.max(2, Math.min(30, Math.round(+$('rn').value) || 8));
  $('rn').value = n;
  try { setGraph(await api(`/api/generate/random?n=${n}&extra=${Math.round(n * 0.75)}`)); } catch (e) { toast(e.message, 'err'); }
};

$('build').onclick = async () => {
  try {
    setGraph(await api('/api/parse', { method: 'POST', body: { text: $('el').value } }));
    toast(`Built a graph with ${plural(state.nodes.length, 'node')} and ${plural(state.edges.length, 'edge')}.`);
  } catch (e) { toast(e.message, 'err'); }
};

// ---------- tabs ----------
const tabs = [...document.querySelectorAll('[role=tab]')];
function selectTab(tab) {
  tabs.forEach((t) => {
    const on = t === tab;
    t.setAttribute('aria-selected', String(on));
    t.tabIndex = on ? 0 : -1;
    $(t.getAttribute('aria-controls')).hidden = !on;
  });
}
tabs.forEach((t, i) => {
  t.onclick = () => selectTab(t);
  t.onkeydown = (ev) => {
    const d = ev.key === 'ArrowRight' ? 1 : ev.key === 'ArrowLeft' ? -1 : 0;
    if (d) { const n = tabs[(i + d + tabs.length) % tabs.length]; selectTab(n); n.focus(); }
  };
});
selectTab(tabs[0]);

// ---------- saved graphs ----------
let savedItems = [];

function renderSavedMarks() {
  document.querySelectorAll('#saved li[data-id]').forEach((li) => li.classList.toggle('current', +li.dataset.id === state.saved.id));
}

async function loadSavedList() {
  const ul = $('saved');
  try {
    savedItems = await api('/api/graphs');
    $('saved-count').textContent = savedItems.length ? String(savedItems.length) : '';
    ul.innerHTML = savedItems.length
      ? savedItems.map((g) => `<li data-id="${g.id}">
          <button class="load" data-load="${g.id}" aria-label="Open ${esc(g.name)}"><b>${esc(g.name)}</b><span>${plural(g.node_count, 'node')}, ${plural(g.edge_count, 'edge')}</span></button>
          <button class="del" data-del="${g.id}" aria-label="Delete ${esc(g.name)}" title="Delete">×</button></li>`).join('')
      : '<li><span class="none">Nothing saved yet. Use “Save graph” above the canvas to keep a graph for later.</span></li>';
    renderSavedMarks();
  } catch (e) {
    ul.innerHTML = `<li><span class="none">${esc(e.message)}</span></li>`;
  }
}

function ask(dialog) {
  return new Promise((resolve) => {
    dialog.addEventListener('close', () => resolve(dialog.returnValue), { once: true });
    dialog.returnValue = '';
    dialog.showModal();
  });
}

$('saved').onclick = async (ev) => {
  const load = ev.target.closest('[data-load]'), del = ev.target.closest('[data-del]');
  try {
    if (load) {
      const g = await api(`/api/graphs/${load.dataset.load}`);
      setGraph(g, { id: g.id, name: g.name });
      toast(`Opened “${g.name}”.`);
    } else if (del) {
      const id = +del.dataset.del;
      const item = savedItems.find((g) => g.id === id);
      $('confirmText').textContent = `“${item ? item.name : 'This graph'}” will be removed for good.`;
      if ((await ask($('confirmDlg'))) !== 'delete') return;
      await api(`/api/graphs/${id}`, { method: 'DELETE' });
      if (state.saved.id === id) state.saved = { id: null, name: '' };
      toast('Deleted.');
      await loadSavedList();
      render();
    }
  } catch (e) { toast(e.message, 'err'); }
};

$('save').onclick = async () => {
  if (!state.nodes.length) { toast('Add at least one node before saving.', 'err'); return; }
  const input = $('saveName');
  input.value = state.saved.name || '';
  $('saveHint').textContent = state.saved.id ? `Keep the name to update “${state.saved.name}”, or change it to save a copy.` : '';
  setTimeout(() => input.select(), 0);
  if ((await ask($('saveDlg'))) !== 'save') return;
  const name = input.value.trim();
  if (!name) return;
  const body = { ...graphPayload(), name };
  try {
    const overwrite = state.saved.id && name === state.saved.name;
    const g = overwrite
      ? await api(`/api/graphs/${state.saved.id}`, { method: 'PUT', body })
      : await api('/api/graphs', { method: 'POST', body });
    state.saved = { id: g.id, name: g.name };
    state.dirty = false;
    toast(overwrite ? `Updated “${g.name}”.` : `Saved “${g.name}”.`);
    await loadSavedList();
    render();
  } catch (e) { toast(e.message, 'err'); }
};

// ---------- algorithm switch ----------
const algoButtons = [...document.querySelectorAll('[data-algo]')];
function setAlgo(algo, { recompute = true } = {}) {
  state.algo = algo;
  try { localStorage.setItem('algo', algo); } catch (e) {}
  algoButtons.forEach((b) => {
    const on = b.dataset.algo === algo;
    b.setAttribute('aria-checked', String(on));
    b.tabIndex = on ? 0 : -1;
  });
  const A = ALGO[algo];
  $('algo-desc').textContent = A.desc;
  $('leg-pick').textContent = A.pickLegend;
  $('leg-cand').hidden = algo !== 'prim';
  $('start-wrap').hidden = algo !== 'prim';
  document.title = `${algo === 'prim' ? "Prim's" : "Kruskal's"} MST Visualizer`;
  if (recompute) invalidate();
}
algoButtons.forEach((b, i) => {
  b.onclick = () => { if (state.algo !== b.dataset.algo) setAlgo(b.dataset.algo); };
  b.onkeydown = (ev) => {
    const d = ev.key === 'ArrowRight' || ev.key === 'ArrowDown' ? 1 : ev.key === 'ArrowLeft' || ev.key === 'ArrowUp' ? -1 : 0;
    if (!d) return;
    ev.preventDefault();
    const next = algoButtons[(i + d + algoButtons.length) % algoButtons.length];
    setAlgo(next.dataset.algo);
    next.focus();
  };
});
setAlgo(state.algo, { recompute: false });

// ---------- theme & health ----------
function syncThemeLabel() {
  const dark = document.documentElement.classList.contains('dark');
  $('theme').setAttribute('aria-label', dark ? 'Switch to light theme' : 'Switch to dark theme');
}
$('theme').onclick = () => {
  const dark = !document.documentElement.classList.contains('dark');
  document.documentElement.classList.toggle('dark', dark);
  try { localStorage.setItem('theme', dark ? 'dark' : 'light'); } catch (e) {}
  syncThemeLabel();
};
syncThemeLabel();

// ---------- boot ----------
api('/api/health').catch(() => {});
loadSavedList();
$('samp').click();
