// ---------- TypeScript Interfaces ----------
export interface Case {
  case_id: string;
  case_name?: string;
  status?: string;
  total_entities?: number;
  severity?: string;
  fir_number?: string;
  date_filed?: string;
  crime_category?: string;
  primary_suspect?: string;
  victim?: string;
  evidences?: string[];
  overlapping_cases?: string[];
  [key: string]: unknown;
}

export interface Entity {
  id?: string;
  entity_id?: string;
  display_name?: string;
  name?: string;
  labels?: string[];
  case_ids?: string[];
  properties?: Record<string, unknown>;
  [key: string]: unknown;
}

export interface Insight {
  insight_id?: string;
  type?: string;
  severity?: string;
  description?: string;
  case_id?: string;
  entities_involved?: string[];
  [key: string]: unknown;
}

export interface GraphNode {
  id: string;
  name?: string;
  labels?: string[];
  properties?: Record<string, unknown>;
}

export interface GraphEdge {
  id?: string;
  source: string;
  target: string;
  type?: string;
  properties?: Record<string, unknown>;
}

export interface HealthStatus {
  status: string;
  database?: string;
  version?: string;
  edition?: string;
  gds_available?: boolean;
  gds_version?: string | null;
  latency_ms?: number;
}

export interface NavOption {
  id: string;
  label: string;
  icon: string;
}

export interface Toast {
  id: number;
  msg: string;
  type: string;
  out: boolean;
}

export type ViewId = 'overview' | 'graph' | 'search' | 'path' | 'rankings' | 'insights' | 'blockchain' | 'cases' | 'ingest';

export type ThemeMode = 'dark' | 'light';

export interface ModalState {
  type: string;
  data?: Record<string, unknown>;
}

export interface AiChatMessage {
  sender: 'user' | 'bot';
  content: string;
  model?: string;
  error?: boolean;
  chips?: string[];
}

export interface PathResult {
  error?: string;
  ambiguous?: boolean;
  message?: string;
  candidates?: Array<{
    person_id: string;
    name: string;
    dob?: string;
    case_ids?: string[];
  }>;
  nodes?: Array<{
    id: string;
    name?: string;
    labels?: string[];
  }>;
  edges?: Array<{
    type: string;
    source: string;
    target: string;
  }>;
  relationships?: Array<{
    id?: string;
    type: string;
    start_node?: string;
    end_node?: string;
    properties?: Record<string, unknown>;
  }>;
  path_length?: number;
  summary?: string;
}

export interface RankingResult {
  rankings: Array<{
    id: string;
    name?: string;
    labels?: string[];
    score: number;
    case_ids?: string[];
  }>;
  total_ranked: number;
  metric?: string;
}

export interface BlockchainBlock {
  block_index?: number;
  case_id?: string;
  document_type?: string;
  hash?: string;
  prev_hash?: string;
  timestamp?: string;
  data?: Record<string, unknown>;
  [key: string]: unknown;
}

// ---------- API Helper ----------
interface ApiErrorDetail {
  detail?: string | Array<{ loc?: string[]; msg: string }> | { message?: string };
  message?: string;
}

interface SendOptions extends RequestInit {
  form?: boolean;
}

export const API = {
  formatError(d: ApiErrorDetail | string | null, status: number): string {
    if (!d) return `HTTP ${status}`;
    if (typeof d === 'string') return d;
    if (d.detail) {
      if (typeof d.detail === 'string') return d.detail;
      if (Array.isArray(d.detail)) {
        return d.detail.map((e) => (e.loc ? e.loc.filter((l) => l !== 'body').join('.') + ': ' : '') + e.msg).join('; ');
      }
      if (typeof d.detail === 'object') return d.detail.message || JSON.stringify(d.detail);
    }
    if (d.message) return d.message;
    return `HTTP ${status}`;
  },
  async get<T = unknown>(url: string): Promise<T> {
    const r = await fetch(url, { headers: { 'Accept': 'application/json' } });
    let d: T | null;
    try { d = await r.json(); } catch { d = null; }
    if (!r.ok) throw new Error(this.formatError(d as unknown as ApiErrorDetail, r.status));
    return d as T;
  },
  async post<T = unknown>(url: string, body: unknown = {}): Promise<T> {
    return this.send<T>(url, {
      method: 'POST',
      body: typeof body === 'string' ? body : JSON.stringify(body)
    });
  },
  async send<T = unknown>(url: string, opts: SendOptions = {}): Promise<T> {
    const headers: Record<string, string> = opts.form ? {} : { 'Content-Type': 'application/json' };
    if (opts.headers) {
      const incomingHeaders = opts.headers as Record<string, string>;
      Object.assign(headers, incomingHeaders);
    }
    const r = await fetch(url, { ...opts, headers });
    let d: T | null;
    try { d = await r.json(); } catch { d = null; }
    if (!r.ok) throw new Error(this.formatError(d as unknown as ApiErrorDetail, r.status));
    return d as T;
  },
  async delete<T = unknown>(url: string, body: unknown = null): Promise<T> {
    const opts: SendOptions = { method: 'DELETE' };
    if (body) {
      opts.headers = { 'Content-Type': 'application/json' } as HeadersInit;
      opts.body = JSON.stringify(body);
    }
    return this.send<T>(url, opts);
  }
};

// ---------- Utility Helpers ----------
export function esc(s: unknown): string {
  return String(s == null ? '' : s);
}

export const LABEL_COLOR: Record<string, string> = {
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

export function getNodeLevel(labels?: string[]): number {
  if (!labels || !labels.length) return 6;
  if (labels.includes('Case')) return 1;
  if (labels.includes('FIR') || labels.includes('PriorCase') || labels.includes('SourceRecord')) return 2;
  if (labels.includes('Person')) return 3;
  if (labels.some((l) => ['Phone', 'BankAccount', 'Vehicle', 'SocialHandle'].includes(l))) return 4;
  if (labels.includes('Transaction')) return 5;
  return 6;
}

export function getDeterministicSeed(str?: string | null): number {
  let hash = 42;
  const s = String(str || 'atlas_seed');
  for (let i = 0; i < s.length; i++) {
    hash = ((hash << 5) - hash) + s.charCodeAt(i);
    hash |= 0;
  }
  return Math.abs(hash) || 42;
}

// ---------- Navigation Config ----------
export const NAV: NavOption[] = [
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

export const TITLES: Record<string, [string, string]> = {
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
