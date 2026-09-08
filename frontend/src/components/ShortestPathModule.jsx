import React, { useState } from 'react';
import { API, esc, LABEL_COLOR } from '../services/api.js';

export function ShortestPathModule({ openEntityModal, addToast }) {
  const [suspect, setSuspect] = useState('');
  const [victim, setVictim] = useState('');
  const [depth, setDepth] = useState(5);
  const [pathResult, setPathResult] = useState(null);
  const [loading, setLoading] = useState(false);

  const doTrace = async (sOverride = null, vOverride = null) => {
    const s = sOverride || suspect.trim();
    const v = vOverride || victim.trim();
    if (!s || !v) { addToast('Specify both suspect and victim', 'info'); return; }
    setLoading(true);

    const sParam = s.toUpperCase().startsWith('P-') || s.toUpperCase().startsWith('PERSON_') ? `suspect_id=${encodeURIComponent(s)}` : `suspect_name=${encodeURIComponent(s)}`;
    const vParam = v.toUpperCase().startsWith('P-') || v.toUpperCase().startsWith('PERSON_') ? `victim_id=${encodeURIComponent(v)}` : `victim_name=${encodeURIComponent(v)}`;

    try {
      const res = await API.get(`/api/cases/shortest-path?${sParam}&${vParam}&max_depth=${depth}`);
      setPathResult(res);
    } catch (e) {
      addToast(e.message, 'err');
      setPathResult({ error: e.message });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <div className="card">
        <div className="card-header"><div className="card-title">Trace Association Path</div></div>
        <div className="row" style={{alignItems:'flex-end'}}>
          <div className="field">
            <label>Suspect (Name or ID)</label>
            <input className="control" value={suspect} onChange={e => setSuspect(e.target.value)} placeholder="e.g. Devendra Sharma or P-001" />
          </div>
          <div className="field">
            <label>Victim (Name or ID)</label>
            <input className="control" value={victim} onChange={e => setVictim(e.target.value)} placeholder="e.g. Rajesh Kumar or P-002" />
          </div>
          <div className="field" style={{maxWidth:'130px'}}>
            <label>Max Hops</label>
            <select className="control" value={depth} onChange={e => setDepth(Number(e.target.value))}>
              {[2,3,5,7,10,15].map(d => <option key={d} value={d}>{d} hops</option>)}
            </select>
          </div>
          <button className="neu-btn primary" disabled={loading} onClick={() => doTrace()}>
            <svg viewBox="0 0 24 24" fill="none" strokeWidth="2" strokeLinecap="round"><path d="M5 12h14m0 0-4-4m4 4-4 4"/></svg>
            Trace Path
          </button>
        </div>
        <div style={{marginTop:'10px', fontSize:'12px', color:'var(--text-faint)'}}>
          Ambiguity safe: if a name resolves to multiple persons, the system presents candidate keys for disambiguation.
        </div>
      </div>

      <div className="card">
        <div className="card-header"><div className="card-title">Path Traversal Result</div></div>
        {loading ? (
          <div><div className="skeleton sk-row"></div><div className="skeleton sk-row"></div></div>
        ) : !pathResult ? (
          <div className="empty">
            <svg viewBox="0 0 24 24" fill="none" strokeWidth="2"><path d="M4 5h12m0 0-3-3m3 3-3 3M4 19h12m0 0-3-3m3 3-3 3M8 8v8"/></svg>
            Enter suspect and victim identifiers to compute graph connectivity.
          </div>
        ) : pathResult.error ? (
          <div className="empty" style={{color:'var(--red)'}}>{pathResult.error}</div>
        ) : pathResult.ambiguous ? (
          <div style={{maxWidth:'640px', margin:'0 auto', textAlign:'left'}}>
            <div style={{color:'var(--amber)', fontWeight:700, fontSize:'15px', marginBottom:'8px'}}>
              ⚠ Ambiguity Detected — Multiple Entities Matched
            </div>
            <p style={{fontSize:'13.5px', color:'var(--text-dim)', marginBottom:'14px'}}>{pathResult.message}</p>
            <div style={{fontSize:'12px', color:'var(--text-faint)', marginBottom:'10px', textTransform:'uppercase', fontWeight:700}}>Matching Candidates:</div>
            {(pathResult.candidates || []).map(c => (
              <div key={c.person_id} className="result-item" style={{cursor:'default'}}>
                <div className="result-main">
                  <div className="result-name">{esc(c.name)} <span className="mono" style={{color:'var(--text-faint)', fontSize:'12px'}}>({esc(c.person_id)})</span></div>
                  <div className="result-sub">DOB: {esc(c.dob || '—')} · Cases: {(c.case_ids || []).join(', ')}</div>
                </div>
                <div style={{display:'flex', gap:'8px'}}>
                  <button className="neu-btn ghost" style={{padding:'4px 8px', fontSize:'11.5px'}} onClick={() => { setSuspect(c.person_id); doTrace(c.person_id, null); }}>Use as Suspect</button>
                  <button className="neu-btn ghost" style={{padding:'4px 8px', fontSize:'11.5px'}} onClick={() => { setVictim(c.person_id); doTrace(null, c.person_id); }}>Use as Victim</button>
                </div>
              </div>
            ))}
          </div>
        ) : !pathResult.nodes || !pathResult.nodes.length ? (
          <div className="empty">{pathResult.summary || 'No association path found between entities within depth limit.'}</div>
        ) : (
          <div style={{maxWidth:'600px', margin:'0 auto'}}>
            <div style={{display:'flex', alignItems:'center', justifyContent:'space-between', marginBottom:'18px'}}>
              <span className="tag open">{pathResult.path_length} Hop Connection</span>
              <span style={{fontSize:'12.5px', color:'var(--text-dim)'}}>{pathResult.summary}</span>
            </div>
            {pathResult.nodes.map((n, i) => (
              <React.Fragment key={n.id}>
                <div style={{display:'flex', alignItems:'center', gap:'12px', padding:'12px 18px', border:'1px solid var(--border)', borderRadius:'12px', background:'var(--surface)'}}>
                  <span className="dot" style={{width:'12px', height:'12px', background: LABEL_COLOR[n.labels?.[0]] || '#94a3b8', borderRadius:'50%'}}></span>
                  <div style={{flex:1}}>
                    <div style={{fontWeight:700, color:'var(--text)', fontSize:'14px'}}>{esc(n.name || n.id)}</div>
                    <div className="mono" style={{color:'var(--text-faint)', fontSize:'11.5px'}}>{esc(n.id)} · {n.labels?.join(', ') || 'Entity'}</div>
                  </div>
                  <button className="neu-btn ghost" style={{padding:'4px 8px', fontSize:'11px'}} onClick={() => openEntityModal(n.id)}>Inspect</button>
                </div>
                {i < pathResult.nodes.length - 1 && (
                  <div style={{display:'flex', alignItems:'center', justifyContent:'center', margin:'4px 0', color:'var(--accent)'}}>
                    <span style={{fontSize:'18px'}}>↓</span>
                    {pathResult.relationships?.[i] && <span className="tag plain mono" style={{marginLeft:'8px'}}>{pathResult.relationships[i].type}</span>}
                  </div>
                )}
              </React.Fragment>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
