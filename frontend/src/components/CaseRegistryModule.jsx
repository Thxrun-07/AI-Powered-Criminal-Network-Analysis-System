import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import * as vis from 'vis-network/standalone';
import { API, esc, LABEL_COLOR, getDeterministicSeed } from '../services/api.js';

export function CaseRegistryModule({ cases, fetchCases, selectedCase, setSelectedCase, openAiDossier, promptDeleteCase, changeView, theme, addToast }) {
  const [statusFilter, setStatusFilter] = useState('');
  const [caseDetail, setCaseDetail] = useState(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const miniGraphRef = useRef(null);
  const miniNetworkInstanceRef = useRef(null);

  const filteredCases = useMemo(() => {
    if (!statusFilter) return cases;
    return cases.filter(c => (c.status || '').toUpperCase() === statusFilter.toUpperCase());
  }, [cases, statusFilter]);

  const loadCaseDetail = useCallback(async (id) => {
    setSelectedCase(id);
    setLoadingDetail(true);
    try {
      const c = await API.get(`/api/cases/${encodeURIComponent(id)}`);
      setCaseDetail(c);
    } catch (e) {
      addToast(e.message, 'err');
      setCaseDetail(null);
    } finally {
      setLoadingDetail(false);
    }
  }, [setSelectedCase, addToast]);

  useEffect(() => {
    if (selectedCase) {
      loadCaseDetail(selectedCase);
    }
  }, [selectedCase, loadCaseDetail]);

  useEffect(() => {
    if (!caseDetail || !miniGraphRef.current) return;
    let isMounted = true;
    async function renderMiniGraph() {
      try {
        const g = await API.get(`/api/graph?case_id=${encodeURIComponent(caseDetail.case_id)}&limit=400`);
        if (!isMounted || !miniGraphRef.current) return;

        const isLight = theme === 'light';
        const seenNodeIds = new Set();
        const nodes = [];
        (g.nodes || []).forEach(n => {
          if (n && n.id && !seenNodeIds.has(n.id)) {
            seenNodeIds.add(n.id);
            nodes.push({
              id: n.id, label: n.name || n.id, size: 12, shape: 'dot',
              color: { background: LABEL_COLOR[n.labels?.[0]] || '#94a3b8', border: isLight ? '#ffffff' : '#070a12' },
              font: { color: isLight ? '#0f172a' : '#cbd5e1', size: 11 }
            });
          }
        });

        const seenEdgeIds = new Set();
        const edges = [];
        (g.edges || []).forEach((e, idx) => {
          if (!e || !e.source || !e.target) return;
          let edgeId = String(e.id || `edge_${e.source}_${e.type}_${e.target}_${idx}`);
          if (seenEdgeIds.has(edgeId)) edgeId = `${edgeId}_${idx}`;
          seenEdgeIds.add(edgeId);
          edges.push({
            id: edgeId, from: e.source, to: e.target, arrows: 'to',
            color: { color: isLight ? 'rgba(51, 65, 85, 0.4)' : 'rgba(148, 163, 184, 0.4)' }
          });
        });

        if (miniNetworkInstanceRef.current) {
          miniNetworkInstanceRef.current.destroy();
          miniNetworkInstanceRef.current = null;
        }

        const seed = getDeterministicSeed(caseDetail.case_id);
        miniNetworkInstanceRef.current = new vis.Network(miniGraphRef.current, { nodes, edges }, {
          layout: { randomSeed: seed, improvedLayout: true },
          physics: {
            solver: 'forceAtlas2Based',
            forceAtlas2Based: { gravitationalConstant: -55, centralGravity: 0.015, springLength: 150, springConstant: 0.07, damping: 0.52, avoidOverlap: 0.85 },
            stabilization: { enabled: true, iterations: 40, updateInterval: 20 }
          },
          nodes: { borderWidth: 2 }, edges: { width: 1.2 }
        });
      } catch (e) {}
    }
    renderMiniGraph();
    return () => {
      isMounted = false;
      if (miniNetworkInstanceRef.current) {
        miniNetworkInstanceRef.current.destroy();
        miniNetworkInstanceRef.current = null;
      }
    };
  }, [caseDetail, theme]);

  return (
    <div>
      <div className="card">
        <div className="card-header">
          <div className="card-title">Case Registry</div>
          <div className="row" style={{gap:'10px'}}>
            <div className="field" style={{maxWidth:'180px'}}>
              <select className="control" value={statusFilter} onChange={e => setStatusFilter(e.target.value)}>
                <option value="">All Statuses</option>
                <option>OPEN</option>
                <option>UNDER_INVESTIGATION</option>
                <option>CHARGED</option>
                <option>CLOSED</option>
              </select>
            </div>
            <button className="neu-btn ghost" onClick={fetchCases}>
              <svg viewBox="0 0 24 24" fill="none" strokeWidth="2" strokeLinecap="round"><path d="M21 12a9 9 0 1 1-2.64-6.36M21 3v6h-6"/></svg>
              Refresh
            </button>
          </div>
        </div>

        <div className="tbl-wrap">
          <table>
            <thead>
              <tr>
                <th>Case Name / ID</th>
                <th>Type</th>
                <th>Priority</th>
                <th>Entities</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {!filteredCases.length ? (
                <tr><td colSpan="6" style={{textAlign:'center', padding:'30px', color:'var(--text-faint)'}}>No cases found matching filter</td></tr>
              ) : (
                filteredCases.map(c => (
                  <tr key={c.case_id} style={selectedCase === c.case_id ? {background:'var(--surface-hover)'} : {}}>
                    <td>
                      <div style={{fontWeight:700, color:'var(--text)'}}>{esc(c.case_name || c.case_id)}</div>
                      <div className="mono" style={{color:'var(--text-faint)', fontSize:'11.5px'}}>{esc(c.case_id)}</div>
                    </td>
                    <td>{esc(c.case_type || '—')}</td>
                    <td><span className={`tag ${(c.priority||'med').toLowerCase()}`}>{esc(c.priority || 'MEDIUM')}</span></td>
                    <td className="mono"><b>{c.total_entities}</b></td>
                    <td><span className={`tag ${(c.status||'open').toLowerCase().includes('close') ? 'closed' : 'open'}`}>{esc(c.status || 'OPEN')}</span></td>
                    <td>
                      <div style={{display:'flex', gap:'6px'}}>
                        <button className="neu-btn ghost" style={{padding:'4px 8px', fontSize:'11.5px'}} onClick={() => loadCaseDetail(c.case_id)}>Inspect</button>
                        <button className="neu-btn ghost" style={{padding:'4px 8px', fontSize:'11.5px', color:'var(--accent)'}} onClick={() => openAiDossier(c.case_id, c.case_name || c.case_id)}>✨ AI Dossier</button>
                        <button className="neu-btn ghost danger" style={{padding:'4px 8px', fontSize:'11.5px'}} onClick={() => promptDeleteCase(c.case_id, c.case_name || c.case_id)}>Delete</button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Case Detail Inspection Card */}
      {selectedCase && (
        <div className="card inspect-container">
          <div className="card-header" style={{borderBottom:'1px solid var(--border)', paddingBottom:'16px', marginBottom:'20px'}}>
            <div style={{display:'flex', flexDirection:'column', gap:'8px'}}>
              <div style={{display:'flex', alignItems:'center', gap:'10px', flexWrap:'wrap'}}>
                <div className="card-title" style={{fontSize:'19px', margin:0}}>
                  <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="var(--accent)" strokeWidth="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>
                  {esc(caseDetail?.case_name || selectedCase)}
                </div>
                <span className="mono tag plain" style={{fontSize:'11px'}}>ID: {esc(selectedCase)}</span>
                {caseDetail?.fir_number && (
                  <span className="tag" style={{background:'rgba(99, 102, 241, 0.14)', color:'var(--accent-secondary)', border:'1px solid rgba(99, 102, 241, 0.3)'}}>
                    📜 FIR No: {esc(caseDetail.fir_number)}
                  </span>
                )}
                {caseDetail?.date && (
                  <span className="tag plain" style={{fontSize:'11px'}}>
                    📅 {esc(caseDetail.date)}
                  </span>
                )}
                {caseDetail?.category_of_crime && (
                  <span className="tag" style={{background:'rgba(2, 132, 199, 0.14)', color:'var(--cyan)', border:'1px solid rgba(2, 132, 199, 0.3)'}}>
                    ⚖️ {esc(caseDetail.category_of_crime)}
                  </span>
                )}
                {caseDetail?.priority && (
                  <span className={`tag ${(caseDetail.priority||'med').toLowerCase()}`}>
                    {esc(caseDetail.priority)}
                  </span>
                )}
                {caseDetail?.status && (
                  <span className={`tag ${(caseDetail.status||'open').toLowerCase().includes('close') ? 'closed' : 'open'}`}>
                    {esc(caseDetail.status)}
                  </span>
                )}
              </div>
            </div>
            <div style={{display:'flex', gap:'8px', alignItems:'center'}}>
              <button className="neu-btn primary" onClick={() => openAiDossier(caseDetail?.case_id || selectedCase, caseDetail?.case_name || selectedCase)}>
                ✨ AI Dossier
              </button>
              <button className="neu-btn ghost" onClick={() => changeView('graph')}>
                View in Graph Explorer →
              </button>
              <button className="neu-btn ghost" onClick={() => setSelectedCase(null)} title="Close Inspection">
                ✕
              </button>
            </div>
          </div>

          {loadingDetail ? (
            <div style={{padding:'20px 0'}}>
              <div className="skeleton sk-row"></div>
              <div className="skeleton sk-row"></div>
            </div>
          ) : !caseDetail ? (
            <div className="empty">Could not load details for case {selectedCase}</div>
          ) : (
            <div>
              {/* Cross-Case Overlap Banner */}
              {caseDetail.case_overlap?.has_overlap ? (
                <div className="overlap-banner alert-overlap-glow">
                  <span style={{fontSize:'22px'}}>⚠️</span>
                  <div style={{flex:1}}>
                    <div style={{fontWeight:700, fontSize:'14px', color:'var(--amber)', marginBottom:'4px'}}>
                      Cross-Case Linkage Detected ({caseDetail.case_overlap.overlap_count} Overlapping Case{caseDetail.case_overlap.overlap_count > 1 ? 's' : ''})
                    </div>
                    <div style={{fontSize:'12.5px', color:'var(--text-dim)', marginBottom:'8px'}}>
                      This investigation shares common suspects, communication nodes, or financial accounts with other registered dockets:
                    </div>
                    <div style={{display:'flex', gap:'8px', flexWrap:'wrap'}}>
                      {caseDetail.case_overlap.overlapping_cases.map((oc, oIdx) => (
                        <div key={oIdx} style={{background:'var(--surface)', border:'1px solid var(--border)', borderRadius:'8px', padding:'6px 12px', fontSize:'12px', display:'flex', alignItems:'center', gap:'8px'}}>
                          <span style={{fontWeight:700, color:'var(--text)'}}>🔗 {esc(oc.case_name || oc.case_id)}</span>
                          <span className="mono tag plain" style={{fontSize:'10px'}}>{esc(oc.case_id)}</span>
                          <span className="tag high" style={{padding:'1px 6px', fontSize:'10px'}}>{oc.shared_count} shared</span>
                          {oc.sample_entities?.length > 0 && (
                            <span style={{color:'var(--text-faint)', fontSize:'11px'}}>({oc.sample_entities.slice(0, 2).join(', ')})</span>
                          )}
                          <button className="neu-btn ghost" style={{padding:'2px 6px', fontSize:'10px', height:'auto'}} onClick={() => loadCaseDetail(oc.case_id)}>Inspect →</button>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              ) : (
                <div className="overlap-banner clean">
                  <span style={{fontSize:'20px'}}>🛡️</span>
                  <div>
                    <div style={{fontWeight:700, fontSize:'13.5px', color:'var(--green)'}}>Isolated Forensic Network</div>
                    <div style={{fontSize:'12px', color:'var(--text-faint)'}}>No multi-case entity contagion or shared suspect overlap detected with other dockets.</div>
                  </div>
                </div>
              )}

              {/* 4-Column Forensic Intelligence Grid */}
              <div className="inspect-grid">
                {/* 1. Primary Suspects */}
                <div className="inspect-subcard">
                  <div className="inspect-subcard-title">
                    <span>🎯</span> Primary Suspects & Targets
                  </div>
                  <div className="inspect-subcard-content">
                    {(caseDetail.primary_suspects || []).length > 0 ? (
                      caseDetail.primary_suspects.slice(0, 4).map((s, idx) => (
                        <div key={idx} className="actor-pill suspect">
                          <span style={{fontWeight:700, color:'var(--text)'}}>{esc(s.name)}</span>
                          <span className="tag crit" style={{fontSize:'10px', padding:'1px 6px'}}>
                            {esc(Array.isArray(s.roles) ? s.roles.join(', ') : (s.roles || 'Suspect'))}
                          </span>
                        </div>
                      ))
                    ) : (
                      <div style={{fontSize:'12.5px', color:'var(--text-faint)', fontStyle:'italic'}}>No primary suspects registered yet in graph.</div>
                    )}
                  </div>
                </div>

                {/* 2. Victims */}
                <div className="inspect-subcard">
                  <div className="inspect-subcard-title">
                    <span>👤</span> Victims & Complainants
                  </div>
                  <div className="inspect-subcard-content">
                    {(caseDetail.victims || []).length > 0 ? (
                      caseDetail.victims.slice(0, 4).map((v, idx) => (
                        <div key={idx} className="actor-pill victim">
                          <span style={{fontWeight:700, color:'var(--text)'}}>{esc(v.name)}</span>
                          <span className="tag open" style={{fontSize:'10px', padding:'1px 6px'}}>
                            {esc(Array.isArray(v.roles) ? v.roles.join(', ') : (v.roles || 'Victim'))}
                          </span>
                        </div>
                      ))
                    ) : (
                      <div style={{fontSize:'12.5px', color:'var(--text-faint)', fontStyle:'italic'}}>No victims or complainants explicitly tagged.</div>
                    )}
                  </div>
                </div>

                {/* 3. Evidences Collected So Far */}
                <div className="inspect-subcard">
                  <div className="inspect-subcard-title">
                    <span>🗂️</span> Evidences Collected So Far
                  </div>
                  <div className="inspect-subcard-content">
                    <div style={{display:'flex', flexWrap:'wrap', gap:'6px'}}>
                      {(caseDetail.evidences_collected || []).map((ev, eIdx) => (
                        <div key={eIdx} className="evidence-chip">
                          <span>{ev.icon}</span>
                          <span>{esc(ev.name)}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                {/* 4. Investigation & Legal Details */}
                <div className="inspect-subcard">
                  <div className="inspect-subcard-title">
                    <span>🏛️</span> Legal & Jurisdictional Record
                  </div>
                  <div className="inspect-subcard-content">
                    <div style={{display:'flex', flexDirection:'column', gap:'6px', fontSize:'12.5px'}}>
                      <div style={{display:'flex', justifyContent:'space-between'}}>
                        <span style={{color:'var(--text-faint)'}}>FIR Number:</span>
                        <span className="mono" style={{fontWeight:700}}>{esc(caseDetail.fir_number || 'N/A')}</span>
                      </div>
                      <div style={{display:'flex', justifyContent:'space-between'}}>
                        <span style={{color:'var(--text-faint)'}}>Crime Category:</span>
                        <span style={{fontWeight:600}}>{esc(caseDetail.category_of_crime || caseDetail.case_type || 'N/A')}</span>
                      </div>
                      <div style={{display:'flex', justifyContent:'space-between'}}>
                        <span style={{color:'var(--text-faint)'}}>Incident / Reg Date:</span>
                        <span>{esc(caseDetail.date || caseDetail.created_at || '—')}</span>
                      </div>
                      <div style={{display:'flex', justifyContent:'space-between'}}>
                        <span style={{color:'var(--text-faint)'}}>Lead Officer:</span>
                        <span>{esc(caseDetail.lead_investigator || 'Special Investigation Unit')}</span>
                      </div>
                      <div style={{display:'flex', justifyContent:'space-between'}}>
                        <span style={{color:'var(--text-faint)'}}>Total Graph Nodes:</span>
                        <span className="mono" style={{fontWeight:700, color:'var(--accent)'}}>{caseDetail.total_entities || 0} entities</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Case Narrative Summary */}
              <div style={{marginBottom:'20px', background:'var(--bg1)', border:'1px solid var(--border)', borderRadius:'12px', padding:'16px'}}>
                <div style={{fontSize:'12px', textTransform:'uppercase', letterSpacing:'0.6px', fontWeight:700, color:'var(--text-faint)', marginBottom:'6px'}}>
                  Investigation Synopsis & Operational Narrative
                </div>
                <div style={{fontSize:'13.5px', color:'var(--text)', lineHeight:1.6}}>
                  {esc(caseDetail.summary || 'No narrative summary provided for this case.')}
                </div>
              </div>

              {/* Subnetwork Topology Mini-Graph */}
              <div style={{background:'var(--bg1)', border:'1px solid var(--border)', borderRadius:'12px', padding:'16px'}}>
                <div style={{display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:'12px'}}>
                  <div style={{fontWeight:700, fontSize:'14px', display:'flex', alignItems:'center', gap:'8px'}}>
                    <span>🕸️</span> Subnetwork Visual Topology
                    <span className="mono tag plain" style={{fontSize:'11px'}}>{caseDetail.total_entities || 0} Nodes</span>
                  </div>
                  <div style={{fontSize:'12px', color:'var(--text-faint)'}}>
                    Interactive sub-topology view · Click node to inspect details
                  </div>
                </div>
                <div style={{width:'100%', height:'360px', borderRadius:'10px', border:'1px solid var(--border)', background:'var(--graph-bg)', overflow:'hidden'}} ref={miniGraphRef}></div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
