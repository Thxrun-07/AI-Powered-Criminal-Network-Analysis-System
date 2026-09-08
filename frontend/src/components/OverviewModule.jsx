import React, { useEffect, useRef, useMemo } from 'react';
import Chart from 'chart.js/auto';
import { API, esc } from '../services/api.js';

export function OverviewModule({ cases, health, insights, setInsights, changeView, openAiDossier }) {
  const chartRef1 = useRef(null);
  const chartRef2 = useRef(null);
  const chartInstance1 = useRef(null);
  const chartInstance2 = useRef(null);

  const openCasesCount = useMemo(() => cases.filter(x => String(x.status || 'OPEN').toUpperCase() !== 'CLOSED').length, [cases]);
  const totalEntities = useMemo(() => cases.reduce((s, x) => s + (x.total_entities || 0), 0), [cases]);
  const critInsights = useMemo(() => (insights || []).filter(i => (i.severity || '').toUpperCase() === 'CRITICAL').length, [insights]);

  useEffect(() => {
    let isMounted = true;
    async function loadData() {
      if (!insights.length && cases.length) {
        try {
          const topCases = cases.slice(0, 4);
          const res = await Promise.all(topCases.map(c => API.get(`/api/cases/${encodeURIComponent(c.case_id)}/insights`).catch(() => [])));
          if (isMounted) setInsights(res.flat());
        } catch (e) {}
      }
      try {
        const g = await API.get('/api/graph?limit=500');
        if (!isMounted) return;
        const counts = {};
        (g.nodes || []).forEach(n => {
          const l = n.labels[0] || 'Entity';
          counts[l] = (counts[l] || 0) + 1;
        });
        if (chartRef1.current) {
          if (chartInstance1.current) chartInstance1.current.destroy();
          chartInstance1.current = new Chart(chartRef1.current, {
            type: 'bar',
            data: {
              labels: Object.keys(counts),
              datasets: [{
                data: Object.values(counts),
                backgroundColor: ['#00d2ff', '#6366f1', '#10b981', '#f59e0b', '#f43f5e', '#a855f7'],
                borderRadius: 6, barPercentage: 0.6
              }]
            },
            options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } }
          });
        }
      } catch (e) {}
    }
    loadData();
    return () => {
      isMounted = false;
      if (chartInstance1.current) {
        chartInstance1.current.destroy();
        chartInstance1.current = null;
      }
    };
  }, [cases, insights.length, setInsights]);

  useEffect(() => {
    const sev = { CRITICAL: 0, HIGH: 0, MEDIUM: 0, LOW: 0 };
    (insights || []).forEach(i => {
      if (sev[i.severity] !== undefined) sev[i.severity]++;
    });
    if (chartRef2.current) {
      if (chartInstance2.current) chartInstance2.current.destroy();
      chartInstance2.current = new Chart(chartRef2.current, {
        type: 'doughnut',
        data: {
          labels: Object.keys(sev),
          datasets: [{
            data: Object.values(sev),
            backgroundColor: ['#f43f5e', '#f59e0b', '#06b6d4', '#10b981']
          }]
        },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'right' } } }
      });
    }
    return () => {
      if (chartInstance2.current) {
        chartInstance2.current.destroy();
        chartInstance2.current = null;
      }
    };
  }, [insights]);

  const isHealthy = health?.status === 'healthy';

  return (
    <div>
      <div className="cards-grid">
        <div className="stat-card" style={{'--glow': 'rgba(0, 210, 255, 0.28)'}}>
          <div className="stat-label">Cases in Database</div>
          <div className="stat-value">{cases.length}</div>
          <div className="stat-foot"><small>{openCasesCount} active / open</small></div>
        </div>
        <div className="stat-card" style={{'--glow': 'rgba(99, 102, 241, 0.25)'}}>
          <div className="stat-label">Total Entities</div>
          <div className="stat-value">{totalEntities.toLocaleString()}</div>
          <div className="stat-foot"><small>indexed in graph</small></div>
        </div>
        <div className="stat-card" style={{'--glow': 'rgba(245, 158, 11, 0.25)'}}>
          <div className="stat-label">Forensic Insights</div>
          <div className="stat-value">{insights.length}</div>
          <div className="stat-foot"><small>{critInsights} critical threats</small></div>
        </div>
        <div className="stat-card" style={{'--glow': isHealthy ? 'rgba(16, 185, 129, 0.35)' : 'rgba(239, 68, 68, 0.35)'}}>
          <div className="stat-label">Database State</div>
          <div className="stat-value" style={{fontSize: '22px'}}>{isHealthy ? 'Connected' : 'Offline'}</div>
          <div className="stat-foot">
            {isHealthy ? <small>Neo4j {health?.version || 'Cluster'} · {Math.round(health?.latency_ms || 0)}ms</small> : <small>Reconnecting to database…</small>}
          </div>
        </div>
      </div>

      <div className="cards-grid" style={{gridTemplateColumns: '2fr 1fr'}}>
        <div className="card">
          <div className="card-header"><div className="card-title">Entity Distribution by Type</div></div>
          <div style={{position:'relative', height:'270px'}}><canvas ref={chartRef1}></canvas></div>
        </div>
        <div className="card">
          <div className="card-header"><div className="card-title">Threat Severity Mix</div></div>
          <div style={{position:'relative', height:'270px'}}><canvas ref={chartRef2}></canvas></div>
        </div>
      </div>

      <div className="card">
        <div className="card-header">
          <div>
            <div className="card-title">Active Investigations</div>
            <div style={{fontSize:'12px', color:'var(--text-faint)', marginTop:'2px'}}>Direct live stream from connected Neo4j knowledge graph</div>
          </div>
          <button className="neu-btn ghost" onClick={() => changeView('cases')}>View all cases →</button>
        </div>
        {!cases.length ? (
          <div className="empty">
            <svg viewBox="0 0 24 24" fill="none" strokeWidth="2"><path d="M3 7a2 2 0 0 1 2-2h5l2 2h9a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7Z"/></svg>
            No cases registered yet. <a href="#" onClick={(e) => { e.preventDefault(); changeView('ingest'); }}>Ingest case data to get started →</a>
          </div>
        ) : (
          <div className="tbl-wrap">
            <table>
              <thead>
                <tr><th>Case Name / ID</th><th>Type</th><th>Entities</th><th>Status</th><th></th></tr>
              </thead>
              <tbody>
                {cases.slice(0, 6).map(x => (
                  <tr key={x.case_id} style={{cursor:'pointer'}} onClick={() => changeView('cases')}>
                    <td>
                      <div style={{fontWeight:700, color:'var(--text)'}}>{esc(x.case_name || x.case_id)}</div>
                      <div className="mono" style={{color:'var(--text-faint)'}}>{esc(x.case_id)}</div>
                    </td>
                    <td>{esc(x.case_type || '—')}</td>
                    <td className="mono">{x.total_entities}</td>
                    <td><span className={`tag ${(x.status || 'open').toLowerCase().includes('close') ? 'closed' : 'open'}`}>{esc(x.status || 'OPEN')}</span></td>
                    <td style={{textAlign:'right'}}>
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth="2" strokeLinecap="round"><path d="M9 6l6 6-6 6"/></svg>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
