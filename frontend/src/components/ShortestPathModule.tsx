import React, { useState } from 'react';
import { API, esc, LABEL_COLOR, PathResult } from '../services/api';

export interface ShortestPathModuleProps {
  openEntityModal: (id: string) => void;
  addToast: (msg: string, type?: string) => void;
}

export function ShortestPathModule({ openEntityModal, addToast }: ShortestPathModuleProps) {
  const [suspect, setSuspect] = useState<string>('');
  const [victim, setVictim] = useState<string>('');
  const [depth, setDepth] = useState<number>(5);
  const [pathResult, setPathResult] = useState<PathResult | null>(null);
  const [loading, setLoading] = useState<boolean>(false);

  const doTrace = async (sOverride: string | null = null, vOverride: string | null = null): Promise<void> => {
    const s = sOverride || suspect.trim();
    const v = vOverride || victim.trim();
    if (!s || !v) {
      addToast('Specify both suspect and victim', 'info');
      return;
    }
    setLoading(true);

    const sParam =
      s.toUpperCase().startsWith('P-') || s.toUpperCase().startsWith('PERSON_')
        ? `suspect_id=${encodeURIComponent(s)}`
        : `suspect_name=${encodeURIComponent(s)}`;
    const vParam =
      v.toUpperCase().startsWith('P-') || v.toUpperCase().startsWith('PERSON_')
        ? `victim_id=${encodeURIComponent(v)}`
        : `victim_name=${encodeURIComponent(v)}`;

    try {
      const res = await API.get<PathResult>(`/api/cases/shortest-path?${sParam}&${vParam}&max_depth=${depth}`);
      setPathResult(res);
    } catch (e: unknown) {
      const errMsg = e instanceof Error ? e.message : String(e);
      addToast(errMsg, 'err');
      setPathResult({ error: errMsg });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <div className="card">
        <div className="card-header">
          <div className="card-title">Trace Association Path</div>
        </div>
        <div className="row flex gap-3.5 items-end flex-wrap" style={{ alignItems: 'flex-end' }}>
          <div className="field flex-1">
            <label>Suspect / Source (Name, Phone, or ID)</label>
            <input
              className="control"
              value={suspect}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => setSuspect(e.target.value)}
              placeholder="e.g. Sameer Khan, Devendra Sharma, P-001"
            />
          </div>
          <div className="field flex-1">
            <label>Victim / Target (Name, Phone, or ID)</label>
            <input
              className="control"
              value={victim}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => setVictim(e.target.value)}
              placeholder="e.g. 9876543010, Rajiv Sen, P-003"
            />
          </div>
          <div className="field max-w-[130px]" style={{ maxWidth: '130px' }}>
            <label>Max Hops</label>
            <select
              className="control"
              value={depth}
              onChange={(e: React.ChangeEvent<HTMLSelectElement>) => setDepth(Number(e.target.value))}
            >
              {[2, 3, 5, 7, 10, 15].map((d) => (
                <option key={d} value={d}>
                  {d} hops
                </option>
              ))}
            </select>
          </div>
          <button className="neu-btn primary flex items-center gap-2 transition" disabled={loading} onClick={() => doTrace()}>
            <svg viewBox="0 0 24 24" fill="none" strokeWidth="2" strokeLinecap="round">
              <path d="M5 12h14m0 0-4-4m4 4-4 4" />
            </svg>
            Trace Path
          </button>
        </div>
        <div className="mt-2.5 text-xs" style={{ marginTop: '10px', fontSize: '12px', color: 'var(--text-faint)' }}>
          Ambiguity safe: if a name resolves to multiple persons, the system presents candidate keys for disambiguation.
        </div>
      </div>

      <div className="card">
        <div className="card-header">
          <div className="card-title">Path Traversal Result</div>
        </div>
        {loading ? (
          <div>
            <div className="skeleton sk-row"></div>
            <div className="skeleton sk-row"></div>
          </div>
        ) : !pathResult ? (
          <div className="empty">
            <svg viewBox="0 0 24 24" fill="none" strokeWidth="2">
              <path d="M4 5h12m0 0-3-3m3 3-3 3M4 19h12m0 0-3-3m3 3-3 3M8 8v8" />
            </svg>
            Enter suspect and victim identifiers to compute graph connectivity.
          </div>
        ) : pathResult.error ? (
          <div className="empty" style={{ color: 'var(--red)' }}>
            {pathResult.error}
          </div>
        ) : pathResult.ambiguous ? (
          <div className="max-w-[640px] mx-auto text-left" style={{ maxWidth: '640px', margin: '0 auto', textAlign: 'left' }}>
            <div className="font-bold text-base mb-2" style={{ color: 'var(--amber)', fontWeight: 700, fontSize: '15px', marginBottom: '8px' }}>
              ⚠ Ambiguity Detected — Multiple Entities Matched
            </div>
            <p className="text-sm mb-3.5" style={{ fontSize: '13.5px', color: 'var(--text-dim)', marginBottom: '14px' }}>
              {pathResult.message}
            </p>
            <div
              className="text-xs uppercase font-bold mb-2.5"
              style={{ fontSize: '12px', color: 'var(--text-faint)', marginBottom: '10px', textTransform: 'uppercase', fontWeight: 700 }}
            >
              Matching Candidates:
            </div>
            {(pathResult.candidates || []).map((c) => (
              <div key={c.person_id} className="result-item flex items-center justify-between" style={{ cursor: 'default' }}>
                <div className="result-main">
                  <div className="result-name font-semibold">
                    {esc(c.name)}{' '}
                    <span className="mono text-xs" style={{ color: 'var(--text-faint)', fontSize: '12px' }}>
                      ({esc(c.person_id)})
                    </span>
                  </div>
                  <div className="result-sub text-xs">
                    DOB: {esc(c.dob || '—')} · Cases: {(c.case_ids || []).join(', ')}
                  </div>
                </div>
                <div className="flex gap-2" style={{ display: 'flex', gap: '8px' }}>
                  <button
                    className="neu-btn ghost transition"
                    style={{ padding: '4px 8px', fontSize: '11.5px' }}
                    onClick={() => {
                      setSuspect(c.person_id);
                      doTrace(c.person_id, null);
                    }}
                  >
                    Use as Suspect
                  </button>
                  <button
                    className="neu-btn ghost transition"
                    style={{ padding: '4px 8px', fontSize: '11.5px' }}
                    onClick={() => {
                      setVictim(c.person_id);
                      doTrace(null, c.person_id);
                    }}
                  >
                    Use as Victim
                  </button>
                </div>
              </div>
            ))}
          </div>
        ) : !pathResult.nodes || !pathResult.nodes.length ? (
          <div className="empty">{pathResult.summary || 'No association path found between entities within depth limit.'}</div>
        ) : (
          <div className="max-w-[600px] mx-auto" style={{ maxWidth: '600px', margin: '0 auto' }}>
            <div
              className="flex items-center justify-between mb-4.5"
              style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '18px' }}
            >
              <span className="tag open font-semibold">{pathResult.path_length} Hop Connection</span>
              <span className="text-xs" style={{ fontSize: '12.5px', color: 'var(--text-dim)' }}>
                {pathResult.summary}
              </span>
            </div>
            {pathResult.nodes.map((n, i) => {
              const firstLabel = n.labels?.[0] || '';
              const dotColor = (firstLabel && LABEL_COLOR[firstLabel]) || '#94a3b8';
              return (
                <React.Fragment key={n.id}>
                  <div
                    className="flex items-center gap-3 p-3 rounded-xl border transition"
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '12px',
                      padding: '12px 18px',
                      border: '1px solid var(--border)',
                      borderRadius: '12px',
                      background: 'var(--surface)'
                    }}
                  >
                    <span
                      className="dot shrink-0"
                      style={{
                        width: '12px',
                        height: '12px',
                        background: dotColor,
                        borderRadius: '50%'
                      }}
                    ></span>
                    <div className="flex-1" style={{ flex: 1 }}>
                      <div className="font-bold text-sm" style={{ fontWeight: 700, color: 'var(--text)', fontSize: '14px' }}>
                        {esc(n.name || n.id)}
                      </div>
                      <div className="mono text-xs" style={{ color: 'var(--text-faint)', fontSize: '11.5px' }}>
                        {esc(n.id)} · {n.labels?.join(', ') || 'Entity'}
                      </div>
                    </div>
                    <button
                      className="neu-btn ghost transition"
                      style={{ padding: '4px 8px', fontSize: '11px' }}
                      onClick={() => openEntityModal(n.id)}
                    >
                      Inspect
                    </button>
                  </div>
                  {i < (pathResult.nodes?.length ?? 0) - 1 && (
                    <div
                      className="flex items-center justify-center my-1"
                      style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '4px 0', color: 'var(--accent)' }}
                    >
                      <span className="text-lg" style={{ fontSize: '18px' }}>
                        ↓
                      </span>
                      {pathResult.relationships?.[i] && (
                        <span className="tag plain mono ml-2" style={{ marginLeft: '8px' }}>
                          {pathResult.relationships[i].type}
                        </span>
                      )}
                    </div>
                  )}
                </React.Fragment>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
