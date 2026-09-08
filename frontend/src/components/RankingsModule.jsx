import React, { useState, useMemo } from 'react';
import { API, esc } from '../services/api.js';

export function RankingsModule({ cases, openEntityModal, addToast }) {
  const [metric, setMetric] = useState('degree');
  const [label, setLabel] = useState('Person');
  const [caseId, setCaseId] = useState('');
  const [limit, setLimit] = useState(15);
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);

  const doCalculate = async () => {
    setLoading(true);
    try {
      const url = `/api/cases/rankings?metric=${metric}&label=${label}&limit=${limit}${caseId ? `&case_id=${encodeURIComponent(caseId)}` : ''}`;
      const r = await API.get(url);
      setResults(r);
    } catch (e) {
      addToast(e.message, 'err');
      setResults({ rankings: [], total_ranked: 0 });
    } finally {
      setLoading(false);
    }
  };

  const maxScore = useMemo(() => results?.rankings?.[0]?.score || 1, [results]);

  return (
    <div>
      <div className="card">
        <div className="card-header"><div className="card-title">Ranking Analysis Configuration</div></div>
        <div className="row" style={{alignItems:'flex-end'}}>
          <div className="field" style={{maxWidth:'200px'}}>
            <label>Centrality Metric</label>
            <select className="control" value={metric} onChange={e => setMetric(e.target.value)}>
              <option value="degree">Degree Centrality</option>
              <option value="weighted_degree">Weighted Degree</option>
              <option value="cross_case_relevance">Cross-Case Relevance</option>
              <option value="pagerank">PageRank</option>
              <option value="betweenness">Betweenness Centrality</option>
            </select>
          </div>
          <div className="field" style={{maxWidth:'180px'}}>
            <label>Entity Category</label>
            <select className="control" value={label} onChange={e => setLabel(e.target.value)}>
              {['Person','Phone','BankAccount','Vehicle','SocialHandle','IPAddress','Location','CellTower'].map(t=><option key={t}>{t}</option>)}
            </select>
          </div>
          <div className="field" style={{maxWidth:'180px'}}>
            <label>Case Filter</label>
            <select className="control" value={caseId} onChange={e => setCaseId(e.target.value)}>
              <option value="">All Cases (Global)</option>
              {cases.map(c => <option key={c.case_id} value={c.case_id}>{esc(c.case_name || c.case_id)}</option>)}
            </select>
          </div>
          <div className="field" style={{maxWidth:'110px'}}>
            <label>Limit</label>
            <input className="control" type="number" value={limit} onChange={e => setLimit(Number(e.target.value))} min="1" max="100" />
          </div>
          <button className="neu-btn primary" disabled={loading} onClick={doCalculate}>Calculate</button>
        </div>
      </div>

      <div className="card">
        <div className="card-header">
          <div className="card-title">Rankings: {metric.replace(/_/g, ' ').toUpperCase()}</div>
          <span className="tag plain">{results ? `${results.total_ranked} Ranked` : '0 Ranked'}</span>
        </div>
        {loading ? (
          <div><div className="skeleton sk-row"></div><div className="skeleton sk-row"></div></div>
        ) : !results ? (
          <div className="empty">
            <svg viewBox="0 0 24 24" fill="none" strokeWidth="2"><path d="M3 17l4-4 4 4 5-5 4 4"/></svg>
            Select parameters above to evaluate influential network nodes.
          </div>
        ) : !results.rankings || !results.rankings.length ? (
          <div className="empty">Data not found</div>
        ) : (
          <div>
            {results.rankings.map((it, i) => (
              <div key={it.id} className="list-row">
                <div style={{display:'flex', alignItems:'center', gap:'14px', flex:1}}>
                  <div style={{
                    width:'30px', height:'30px', borderRadius:'10px', display:'grid', placeItems:'center', fontWeight:800, fontSize:'13px',
                    background: i===0 ? 'var(--accent-gradient)' : i===1 ? 'rgba(99,102,241,0.25)' : i===2 ? 'rgba(245,158,11,0.25)' : 'var(--surface-hover)',
                    color: i===0 ? '#fff' : 'var(--text)'
                  }}>
                    {i + 1}
                  </div>
                  <div>
                    <div className="l-name">{esc(it.name || it.id)}</div>
                    <div className="l-sub mono">{esc(it.id)} · {(it.case_ids || []).join(', ')}</div>
                  </div>
                </div>
                <div style={{display:'flex', alignItems:'center', gap:'16px', minWidth:'200px'}}>
                  <div style={{flex:1, height:'8px', borderRadius:'6px', background:'var(--bg1)', overflow:'hidden', border:'1px solid var(--border)'}}>
                    <div style={{height:'100%', width:`${Math.max(5, (it.score / maxScore) * 100)}%`, background:'var(--accent-gradient)', borderRadius:'6px'}}></div>
                  </div>
                  <span className="mono" style={{fontWeight:700, color:'var(--text)', minWidth:'48px', textAlign:'right'}}>{Number(it.score).toFixed(it.score < 10 ? 2 : 0)}</span>
                  <button className="neu-btn ghost" style={{padding:'3px 8px', fontSize:'11px'}} onClick={() => openEntityModal(it.id)}>Profile</button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
