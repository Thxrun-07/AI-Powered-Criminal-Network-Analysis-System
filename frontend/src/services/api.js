// ---------- API Helper ----------
export const API = {
  formatError(d, status) {
    if (!d) return `HTTP ${status}`;
    if (typeof d === 'string') return d;
    if (d.detail) {
      if (typeof d.detail === 'string') return d.detail;
      if (Array.isArray(d.detail)) {
        return d.detail.map(e => (e.loc ? e.loc.filter(l => l !== 'body').join('.') + ': ' : '') + e.msg).join('; ');
      }
      if (typeof d.detail === 'object') return d.detail.message || JSON.stringify(d.detail);
    }
    if (d.message) return d.message;
    return `HTTP ${status}`;
  },
  async get(url) {
    const r = await fetch(url, { headers: { 'Accept': 'application/json' } });
    let d;
    try { d = await r.json(); } catch(e) { d = null; }
    if (!r.ok) throw new Error(this.formatError(d, r.status));
    return d;
  },
  async post(url, body = {}) {
    return this.send(url, {
      method: 'POST',
      body: typeof body === 'string' ? body : JSON.stringify(body)
    });
  },
  async send(url, opts = {}) {
    const headers = opts.form ? {} : { 'Content-Type': 'application/json' };
    if (opts.headers) Object.assign(headers, opts.headers);
    const r = await fetch(url, { ...opts, headers });
    let d;
    try { d = await r.json(); } catch(e) { d = null; }
    if (!r.ok) throw new Error(this.formatError(d, r.status));
    return d;
  },
  async delete(url, body = null) {
    const opts = { method: 'DELETE' };
    if (body) {
      opts.headers = { 'Content-Type': 'application/json' };
      opts.body = JSON.stringify(body);
    }
    return this.send(url, opts);
  }
};

// ---------- Utility Helpers ----------
export function esc(s) {
  return String(s == null ? '' : s);
}

export const LABEL_COLOR = {
  Person: '#6366f1',
  Phone: '#00d2ff',
  BankAccount: '#10b981',
  Vehicle: '#f59e0b',
  SocialHandle: '#a855f7',
  IPAddress: '#f43f5e',
  Location: '#fb7185',
  CellTower: '#14b8a6',
  FIR: '#ec4899',
  PriorCase: '#94a3b8',
  Case: '#38bdf8',
  Transaction: '#10b981',
  SourceRecord: '#64748b',
  Organization: '#3b82f6'
};

export function getNodeLevel(labels) {
  if (!labels || !labels.length) return 6;
  if (labels.includes('Case')) return 1;
  if (labels.includes('FIR') || labels.includes('PriorCase') || labels.includes('SourceRecord')) return 2;
  if (labels.includes('Person')) return 3;
  if (labels.some(l => ['Phone', 'BankAccount', 'Vehicle', 'SocialHandle'].includes(l))) return 4;
  if (labels.includes('Transaction')) return 5;
  return 6;
}

export function getDeterministicSeed(str) {
  let hash = 42;
  const s = String(str || 'atlas_seed');
  for (let i = 0; i < s.length; i++) {
    hash = ((hash << 5) - hash) + s.charCodeAt(i);
    hash |= 0;
  }
  return Math.abs(hash) || 42;
}

// ---------- Navigation Config ----------
export const NAV = [
  { id: 'overview', label: 'Command Center', icon: 'M4 13 9 4l5 9H4Zm6 0 5-8 5 8h-10Z' },
  { id: 'graph', label: 'Graph Explorer', icon: 'M12 3a2 2 0 0 1 2 2c0 .4-.1.8-.3 1.1l3.4 5.4c.3-.1.6-.2.9-.2a2 2 0 1 1 0 4c-.3 0-.6-.1-.9-.2l-3.4 5.4c.2.3.3.7.3 1.1a2 2 0 1 1-3.6-1.1L8.9 15.5c-.3.1-.6.2-.9.2a2 2 0 1 1 0-4c.3 0 .6.1.8.2l3.4-5.4c-.2-.3-.3-.7-.3-1.1a2 2 0 0 1 2-2Z' },
  { id: 'search', label: 'Entity Search', icon: 'M11 19a8 8 0 1 0 0-16 8 8 0 0 0 0 16Zm10 2-4.35-4.35' },
  { id: 'path', label: 'Shortest Path', icon: 'M4 5h12m0 0-3-3m3 3-3 3M4 19h12m0 0-3-3m3 3-3 3M8 8v8' },
  { id: 'rankings', label: 'Rankings', icon: 'M3 17l4-4 4 4 5-5 4 4' },
  { id: 'insights', label: 'Pattern Insights', icon: 'M12 3l1.9 5.6L19 10l-5.1 1.9L12 17.5l-1.9-5.6L5 10l5.1-1.4L12 3Z' },
  { id: 'blockchain', label: 'Chain of Custody', icon: 'M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z' },
  { id: 'cases', label: 'Case Registry', icon: 'M3 7a2 2 0 0 1 2-2h5l2 2h9a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7Z' },
  { id: 'ingest', label: 'Data Ingestion', icon: 'M12 5v14m-7-7h14' }
];

export const TITLES = {
  overview: ['Command Center', 'Ecosystem health metrics, top entities and active investigations'],
  graph: ['Graph Explorer', 'Interactive topological network visualization'],
  search: ['Entity Search', 'Fast multi-property search across people, phones, bank accounts, VINs'],
  path: ['Shortest Path Analysis', 'Trace shortest association paths between suspect and victim'],
  rankings: ['Centrality Rankings', 'Degree, PageRank, betweenness, and cross-case relevance'],
  insights: ['Forensic Insights', 'Automated graph intelligence and anomaly detection'],
  blockchain: ['Chain of Custody Ledger', 'Cryptographic SHA-256 Merkle block proof & anti-tampering evidence verification'],
  cases: ['Case Registry', 'Manage cases, entity breakdowns, and case deletion'],
  ingest: ['Data Ingestion', 'Ingest structured case JSON, CSV files, or raw narratives']
};
