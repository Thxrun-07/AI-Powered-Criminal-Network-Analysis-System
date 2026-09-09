import React, { useState, useMemo } from 'react';
import { API, esc, Case, RankingResult } from '../services/api';

export interface RankingsModuleProps {
  cases: Case[];
  openEntityModal: (id: string) => void;
  addToast: (msg: string, type?: string) => void;
}

export function RankingsModule({ cases, openEntityModal, addToast }: RankingsModuleProps) {
  const [metric, setMetric] = useState<string>('degree');
  const [label, setLabel] = useState<string>('Person');
  const [caseId, setCaseId] = useState<string>('');
  const [limit, setLimit] = useState<number>(15);
  const [results, setResults] = useState<RankingResult | null>(null);
  const [loading, setLoading] = useState<boolean>(false);

  const doCalculate = async (): Promise<void> => {
    setLoading(true);
    try {
      const url = `/api/cases/rankings?metric=${metric}&label=${label}&limit=${limit}${
        caseId ? `&case_id=${encodeURIComponent(caseId)}` : ''
      }`;
      const r = await API.get<RankingResult>(url);
      setResults(r);
    } catch (e: unknown) {
      const errMsg = e instanceof Error ? e.message : String(e);
      addToast(errMsg, 'err');
      setResults({ rankings: [], total_ranked: 0 });
    } finally {
      setLoading(false);
    }
  };

  const maxScore = useMemo<number>(() => results?.rankings?.[0]?.score || 1, [results]);

  return (
    <div>
      <div className="card">
        <div className="card-header">
          <div className="card-title">Ranking Analysis Configuration</div>
        </div>
        <div className="row flex gap-3.5 items-end flex-wrap" style={{ alignItems: 'flex-end' }}>
          <div className="field max-w-[200px]" style={{ maxWidth: '200px' }}>
            <label>Centrality Metric</label>
            <select
              className="control"
              value={metric}
              onChange={(e: React.ChangeEvent<HTMLSelectElement>) => setMetric(e.target.value)}
            >
              <option value="degree">Degree Centrality</option>
              <option value="weighted_degree">Weighted Degree</option>
              <option value="cross_case_relevance">Cross-Case Relevance</option>
              <option value="pagerank">PageRank</option>
              <option value="betweenness">Betweenness Centrality</option>
            </select>
          </div>
          <div className="field max-w-[180px]" style={{ maxWidth: '180px' }}>
            <label>Entity Category</label>
            <select
              className="control"
              value={label}
              onChange={(e: React.ChangeEvent<HTMLSelectElement>) => setLabel(e.target.value)}
            >
              {['Person', 'Phone', 'BankAccount', 'Vehicle', 'SocialHandle', 'IPAddress', 'Location', 'CellTower'].map(
                (t) => (
                  <option key={t}>{t}</option>
                )
              )}
            </select>
          </div>
          <div className="field max-w-[180px]" style={{ maxWidth: '180px' }}>
            <label>Case Filter</label>
            <select
              className="control"
              value={caseId}
              onChange={(e: React.ChangeEvent<HTMLSelectElement>) => setCaseId(e.target.value)}
            >
              <option value="">All Cases (Global)</option>
              {cases.map((c) => (
                <option key={c.case_id} value={c.case_id}>
                  {esc(c.case_name || c.case_id)}
                </option>
              ))}
            </select>
          </div>
          <div className="field max-w-[110px]" style={{ maxWidth: '110px' }}>
            <label>Limit</label>
            <input
              className="control"
              type="number"
              value={limit}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => setLimit(Number(e.target.value))}
              min="1"
              max="100"
            />
          </div>
          <button className="neu-btn primary transition" disabled={loading} onClick={doCalculate}>
            Calculate
          </button>
        </div>
      </div>

      <div className="card">
        <div className="card-header flex items-center justify-between">
          <div className="card-title">Rankings: {metric.replace(/_/g, ' ').toUpperCase()}</div>
          <span className="tag plain">{results ? `${results.total_ranked} Ranked` : '0 Ranked'}</span>
        </div>
        {loading ? (
          <div>
            <div className="skeleton sk-row"></div>
            <div className="skeleton sk-row"></div>
          </div>
        ) : !results ? (
          <div className="empty">
            <svg viewBox="0 0 24 24" fill="none" strokeWidth="2">
              <path d="M3 17l4-4 4 4 5-5 4 4" />
            </svg>
            Select parameters above to evaluate influential network nodes.
          </div>
        ) : !results.rankings || !results.rankings.length ? (
          <div className="empty">Data not found</div>
        ) : (
          <div>
            {results.rankings.map((it, i) => (
              <div key={it.id} className="list-row flex items-center justify-between gap-3">
                <div className="flex items-center gap-3.5 flex-1" style={{ display: 'flex', alignItems: 'center', gap: '14px', flex: 1 }}>
                  <div
                    className="w-[30px] h-[30px] rounded-[10px] grid place-items-center font-extrabold text-xs shrink-0"
                    style={{
                      width: '30px',
                      height: '30px',
                      borderRadius: '10px',
                      display: 'grid',
                      placeItems: 'center',
                      fontWeight: 800,
                      fontSize: '13px',
                      background:
                        i === 0
                          ? 'var(--accent-gradient)'
                          : i === 1
                          ? 'rgba(99,102,241,0.25)'
                          : i === 2
                          ? 'rgba(245,158,11,0.25)'
                          : 'var(--surface-hover)',
                      color: i === 0 ? '#fff' : 'var(--text)'
                    }}
                  >
                    {i + 1}
                  </div>
                  <div>
                    <div className="l-name font-semibold">{esc(it.name || it.id)}</div>
                    <div className="l-sub mono text-xs">{esc(it.id)} · {(it.case_ids || []).join(', ')}</div>
                  </div>
                </div>
                <div className="flex items-center gap-4 min-w-[200px]" style={{ display: 'flex', alignItems: 'center', gap: '16px', minWidth: '200px' }}>
                  <div
                    className="flex-1 h-2 rounded-md bg-[var(--bg1)] overflow-hidden border border-[var(--border)]"
                    style={{
                      flex: 1,
                      height: '8px',
                      borderRadius: '6px',
                      background: 'var(--bg1)',
                      overflow: 'hidden',
                      border: '1px solid var(--border)'
                    }}
                  >
                    <div
                      style={{
                        height: '100%',
                        width: `${Math.max(5, (it.score / maxScore) * 100)}%`,
                        background: 'var(--accent-gradient)',
                        borderRadius: '6px'
                      }}
                    ></div>
                  </div>
                  <span
                    className="mono font-bold min-w-[48px] text-right text-xs"
                    style={{ fontWeight: 700, color: 'var(--text)', minWidth: '48px', textAlign: 'right' }}
                  >
                    {Number(it.score).toFixed(it.score < 10 ? 2 : 0)}
                  </span>
                  <button
                    className="neu-btn ghost transition"
                    style={{ padding: '3px 8px', fontSize: '11px' }}
                    onClick={() => openEntityModal(it.id)}
                  >
                    Profile
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
