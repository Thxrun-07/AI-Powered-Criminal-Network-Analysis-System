import React from 'react';
import { NAV } from '../services/api.js';

export function Sidebar({ view, changeView, theme, toggleTheme, sidebarOpen, setSidebarOpen, promptResetDatabase }) {
  return (
    <aside className={`sidebar ${sidebarOpen ? 'open' : ''}`}>
      <div className="brand">
        <div className="brand-logo">
          <svg viewBox="0 0 24 24" fill="none" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="6" cy="6" r="3"/><circle cx="18" cy="7" r="3"/><circle cx="12" cy="18" r="3"/>
            <path d="M8.7 8.1 10 10M15.2 9l-.6 2M10 12.6l1 2.4"/>
          </svg>
        </div>
        <div>
          <div className="brand-name">Atlas</div>
          <div className="brand-sub">Graph Intelligence</div>
        </div>
      </div>
      <div className="nav-label">Analytics Modules</div>
      <nav className="nav">
        {NAV.map(n => (
          <button key={n.id} className={`nav-item ${view === n.id ? 'active' : ''}`} onClick={() => changeView(n.id)}>
            <svg viewBox="0 0 24 24" fill="none" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d={n.icon}/></svg>
            <span>{n.label}</span>
          </button>
        ))}
      </nav>
      <div className="side-foot">
        <div>Case-Graph Intelligence Engine</div>
        <div className="mono" style={{color:'var(--text-faint)', fontSize:'10.5px'}}>Neo4j GDS · FastAPI React 19</div>
        <div className="side-foot-actions">
          <button className="neu-btn ghost danger" style={{padding:'6px 10px', fontSize:'11px'}} onClick={promptResetDatabase}>
            <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" strokeWidth="2"><path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
            Reset DB
          </button>
          <button className="theme-btn" onClick={toggleTheme} title="Toggle Light/Dark Theme">
            <svg viewBox="0 0 24 24" fill="none" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              {theme === 'dark' ? (
                <React.Fragment>
                  <circle cx="12" cy="12" r="5"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/>
                </React.Fragment>
              ) : (
                <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
              )}
            </svg>
          </button>
        </div>
      </div>
    </aside>
  );
}

export function Topbar({ view, health, theme, toggleTheme, setSidebarOpen }) {
  const TITLES = {
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

  return (
    <div className="topbar">
      <div style={{display:'flex', alignItems:'center', gap:'14px'}}>
        <button className="hamburger" onClick={() => setSidebarOpen(prev => !prev)}>
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M3 6h18M3 12h18M3 18h18"/></svg>
        </button>
        <div className="topbar-title">
          <h1>{TITLES[view]?.[0] || 'Command Center'}</h1>
          <p>{TITLES[view]?.[1] || 'Crime & Case Graph Intelligence'}</p>
        </div>
      </div>
      <div className="topbar-actions">
        <div className="status-pill">
          <span className={`status-dot ${health ? 'ok' : 'bad'}`}></span>
          <span>{health ? 'Database Active' : 'Connecting…'}</span>
          {health && <span className="status-meta">{Math.round(health.latency_ms)}ms</span>}
        </div>
        <button className="theme-btn" onClick={toggleTheme} title="Toggle Theme">
          <svg viewBox="0 0 24 24" fill="none" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            {theme === 'dark' ? (
              <circle cx="12" cy="12" r="5"/>
            ) : (
              <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
            )}
          </svg>
        </button>
      </div>
    </div>
  );
}
