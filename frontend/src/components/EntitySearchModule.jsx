import React, { useState } from 'react';
import { API, esc } from '../services/api.js';

export function EntitySearchModule({ openEntityModal, addToast }) {
  const [query, setQuery] = useState('');
  const [category, setCategory] = useState('');
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);

  const doSearch = async () => {
    if (!query.trim()) { addToast('Please specify a search query', 'info'); return; }
    setLoading(true);
    try {
      const res = await API.get(`/api/entities/search?q=${encodeURIComponent(query.trim())}${category ? `&entity_type=${category}` : ''}&limit=50`);
      setResults(res);
    } catch (e) {
      setResults([]);
      addToast(e.message, 'err');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <div className="card">
        <div className="card-header"><div className="card-title">Entity Knowledge Search</div></div>
        <div className="row" style={{alignItems:'flex-end'}}>
          <div className="field" style={{flex:2}}>
            <label>Search Query</label>
            <input className="control" value={query} onChange={e => setQuery(e.target.value)} onKeyDown={e => { if (e.key === 'Enter') doSearch(); }} placeholder="Enter name, phone (+91...), account number, VIN, license plate, or handle…" />
          </div>
          <div className="field" style={{maxWidth:'200px'}}>
            <label>Entity Category</label>
            <select className="control" value={category} onChange={e => setCategory(e.target.value)}>
              <option value="">All Categories</option>
              {['Person','Phone','BankAccount','Vehicle','SocialHandle','IPAddress','Location','CellTower','Case','FIR'].map(t=><option key={t}>{t}</option>)}
            </select>
          </div>
          <button className="neu-btn primary" disabled={loading} onClick={doSearch}>
            <svg viewBox="0 0 24 24" fill="none" strokeWidth="2" strokeLinecap="round"><path d="M11 19a8 8 0 1 0 0-16 8 8 0 0 0 0 16Zm10 2-4.35-4.35"/></svg>
            Search
          </button>
        </div>
      </div>

      <div className="card">
        <div className="card-header">
          <div className="card-title">Search Results</div>
          <span className="tag plain">{results ? `${results.length} matches` : '0 matches'}</span>
        </div>
        {loading ? (
          <div><div className="skeleton sk-row"></div><div className="skeleton sk-row"></div></div>
        ) : !results ? (
          <div className="empty">
            <svg viewBox="0 0 24 24" fill="none" strokeWidth="2"><path d="M11 19a8 8 0 1 0 0-16 8 8 0 0 0 0 16Zm10 2-4.35-4.35"/></svg>
            Execute a search query above to inspect entity profiles.
          </div>
        ) : !results.length ? (
          <div className="empty">No entity matches found for "{query}". Try searching by partial name or number.</div>
        ) : (
          <div>
            {results.map(r => (
              <div key={r.entity_id} className="result-item" onClick={() => openEntityModal(r.entity_id)}>
                <div className="result-main">
                  <div className="result-name">{esc(r.display_name || r.entity_id)}</div>
                  <div className="result-sub mono">{esc(r.entity_id)}</div>
                </div>
                <div style={{display:'flex', alignItems:'center', gap:'10px'}}>
                  <span className="tag plain">{r.labels.slice(0, 3).join(', ')}</span>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth="2" strokeLinecap="round"><path d="M9 6l6 6-6 6"/></svg>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
