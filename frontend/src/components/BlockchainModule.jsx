import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { API, esc } from '../services/api.js';

export function BlockchainModule({ cases, fetchCases, addToast }) {
  const [blocks, setBlocks] = useState([]);
  const [search, setSearch] = useState('');
  const [expandedCases, setExpandedCases] = useState(new Set());
  const [loading, setLoading] = useState(false);
  const [auditing, setAuditing] = useState(false);
  const [liveAuditMap, setLiveAuditMap] = useState({});

  const fetchLedger = useCallback(async () => {
    setLoading(true);
    try {
      if (!cases.length) await fetchCases();
      const data = await API.get('/api/v1/blockchain/ledger');
      setBlocks(data.blocks || []);
    } catch (e) {
      addToast(e.message, 'err');
    } finally {
      setLoading(false);
    }
  }, [cases.length, fetchCases, addToast]);

  useEffect(() => {
    fetchLedger();
  }, [fetchLedger]);

  const toggleCaseExpand = (cid) => {
    setExpandedCases(prev => {
      const next = new Set(prev);
      if (next.has(cid)) next.delete(cid);
      else next.add(cid);
      return next;
    });
  };

  const expandAll = (expand) => {
    if (expand) {
      const ids = [...new Set(blocks.map(b => b.case_id))];
      setExpandedCases(new Set(ids));
    } else {
      setExpandedCases(new Set());
    }
  };

  const caseMap = useMemo(() => {
    const map = {};
    blocks.forEach(b => {
      const cid = b.case_id || 'UNKNOWN';
      if (cid === 'SYSTEM_GENESIS' || b.document_type === 'SYSTEM_GENESIS') return;
      if (!map[cid]) map[cid] = [];
      map[cid].push(b);
    });
    return map;
  }, [blocks]);

  const caseIds = useMemo(() => {
    const regIds = cases.map(c => c.case_id).filter(id => id && id !== 'SYSTEM_GENESIS');
    const ledIds = Object.keys(caseMap).filter(id => id !== 'SYSTEM_GENESIS');
    return [...new Set([...regIds, ...ledIds])].sort();
  }, [cases, caseMap]);

  const runLiveAudit = useCallback(async () => {
    if (!caseIds.length) return;
    setAuditing(true);
    try {
      const results = {};
      await Promise.all(caseIds.map(async (cid) => {
        try {
          const res = await API.get(`/api/v1/blockchain/verify-case/${encodeURIComponent(cid)}`);
          results[cid] = res;
        } catch (e) {
          results[cid] = { status: 'ERROR', message: e.message };
        }
      }));
      setLiveAuditMap(results);
    } catch (e) {
      addToast(`Live audit error: ${e.message}`, 'err');
    } finally {
      setAuditing(false);
    }
  }, [caseIds, addToast]);

  useEffect(() => {
    if (caseIds.length > 0) {
      runLiveAudit();
    }
  }, [caseIds.length, runLiveAudit]);

  const totalLedgerTampered = useMemo(() => blocks.filter(b => b.is_valid === false).length, [blocks]);
  const totalLiveTamperedCases = useMemo(() => {
    return Object.values(liveAuditMap).filter(a => a.status === 'TAMPERED').length;
  }, [liveAuditMap]);

  const filteredCaseIds = useMemo(() => {
    const q = search.toLowerCase().trim();
    if (!q) return caseIds;
    return caseIds.filter(cid => {
      const cObj = cases.find(c => c.case_id === cid);
      const cName = cObj?.case_name || cid;
      if (cid.toLowerCase().includes(q) || cName.toLowerCase().includes(q)) return true;
      const caseBlocks = caseMap[cid] || [];
      return caseBlocks.some(b => 
        (b.document_name || '').toLowerCase().includes(q) || 
        (b.document_type || '').toLowerCase().includes(q) ||
        (b.evidence_hash || '').toLowerCase().includes(q)
      );
    });
  }, [caseIds, cases, caseMap, search]);

  const docIconMap = { FIR: '📜', CDR_LOG: '📞', BANK_STATEMENT: '💳', SURVEILLANCE_LOG: '📹', INTEL_REPORT: '📄', CASE_MASTER: '📂' };

  return (
    <div>
      <div className="card">
        <div className="card-header">
          <div className="card-title">
            <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="var(--accent)" strokeWidth="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
            Blockchain Evidence Chain of Custody
          </div>
          <div className="row" style={{gap:'10px'}}>
            <div className="field" style={{minWidth:'260px'}}>
              <input className="control" value={search} onChange={e => setSearch(e.target.value)} placeholder="Search case ID or document..." />
            </div>
            <button className="neu-btn primary" onClick={() => { fetchLedger(); runLiveAudit(); }} disabled={loading || auditing}>
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 12a9 9 0 1 1-2.64-6.36M21 3v6h-6"/></svg>
              {auditing ? 'Auditing Database…' : 'Run Verification Audit'}
            </button>
          </div>
        </div>
        <div className="cards-grid" style={{gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', marginTop:'10px'}}>
          <div className="stat-card" style={{'--glow': (totalLedgerTampered > 0 || totalLiveTamperedCases > 0) ? 'rgba(239, 68, 68, 0.3)' : 'rgba(16, 185, 129, 0.2)'}}>
            <div className="stat-label">Chain-of-Custody Status</div>
            <div className="stat-value" style={{fontSize:'18px', marginTop:'14px', color: (totalLedgerTampered > 0 || totalLiveTamperedCases > 0) ? '#ef4444' : '#10b981'}}>
              {(totalLedgerTampered > 0 || totalLiveTamperedCases > 0) ? `🔴 ${totalLiveTamperedCases || totalLedgerTampered} TAMPERED DETECTED` : '🟢 100% VERIFIED'}
            </div>
          </div>
          <div className="stat-card" style={{'--glow': 'rgba(99, 102, 241, 0.2)'}}>
            <div className="stat-label">Encryption & Proof</div>
            <div className="stat-value" style={{fontSize:'18px', marginTop:'14px'}}>SHA-256 Merkle Proof</div>
          </div>
          <div className="stat-card" style={{'--glow': 'rgba(6, 182, 212, 0.2)'}}>
            <div className="stat-label">Live Database Audit</div>
            <div className="stat-value" style={{fontSize:'18px', marginTop:'14px', color: totalLiveTamperedCases > 0 ? '#ef4444' : 'var(--accent)'}}>
              {auditing ? 'Auditing Graph…' : totalLiveTamperedCases > 0 ? `${totalLiveTamperedCases} Case Mismatch` : 'Neo4j Graph Synced'}
            </div>
          </div>
        </div>
      </div>

      <div className="card">
        <div className="card-header">
          <div className="card-title">Investigation Cases & Evidence Verification</div>
          <div style={{display:'flex', gap:'10px', alignItems:'center'}}>
            <button className="neu-btn ghost" style={{padding:'4px 10px', fontSize:'11.5px'}} onClick={() => expandAll(true)}>Expand All</button>
            <button className="neu-btn ghost" style={{padding:'4px 10px', fontSize:'11.5px'}} onClick={() => expandAll(false)}>Collapse All</button>
            <span className="tag plain">{filteredCaseIds.length} Cases</span>
          </div>
        </div>

        {loading ? (
          <div className="skeleton sk-row"></div>
        ) : !filteredCaseIds.length ? (
          <div className="empty">No blockchain cases recorded matching filter query.</div>
        ) : (
          <div style={{display:'flex', flexDirection:'column', gap:'12px', marginTop:'10px'}}>
            {filteredCaseIds.map(cid => {
              const caseBlocks = caseMap[cid] || [];
              const cObj = cases.find(c => c.case_id === cid);
              const caseName = cObj?.case_name || cid;
              const liveAudit = liveAuditMap[cid];
              const isBlockTampered = caseBlocks.some(b => b.is_valid === false);
              const isLiveTampered = liveAudit && liveAudit.status === 'TAMPERED';
              const isTampered = isBlockTampered || isLiveTampered;
              const isExpanded = expandedCases.has(cid);

              return (
                <div key={cid} className="card" style={{marginBottom:0, border: isTampered ? '1px solid rgba(239,68,68,0.5)' : '1px solid var(--border)'}}>
                  <div style={{display:'flex', alignItems:'center', justifyContent: 'space-between', cursor:'pointer', userSelect:'none'}} onClick={() => toggleCaseExpand(cid)}>
                    <div style={{display:'flex', alignItems:'center', gap:'12px'}}>
                      <span style={{fontSize:'20px', color: isTampered ? '#ef4444' : 'var(--accent)'}}>📁</span>
                      <div>
                        <div style={{fontWeight:700, fontSize:'15px', color:'var(--text)'}}>{esc(caseName)}</div>
                        <div className="mono" style={{fontSize:'12px', color:'var(--text-faint)'}}>Case ID: {esc(cid)} · {caseBlocks.length} Document Blocks</div>
                      </div>
                    </div>
                    <div style={{display:'flex', alignItems:'center', gap:'14px'}}>
                      {isTampered ? (
                        <span className="tag crit" style={{background:'rgba(239,68,68,0.2)', color:'#ef4444', border:'1px solid rgba(239,68,68,0.4)', fontWeight:700}}>
                          🔴 {isLiveTampered ? `DATABASE TAMPERED (${(liveAudit?.tampered_document_types || []).join(', ') || 'Graph Mismatch'})` : 'BLOCK TAMPERED'}
                        </span>
                      ) : (
                        <span className="tag low" style={{background:'rgba(16,185,129,0.15)', color:'#10b981', border:'1px solid rgba(16,185,129,0.3)', fontWeight:700}}>🟢 VERIFIED</span>
                      )}
                      <span style={{fontSize:'13px', color:'var(--accent)', fontWeight:600}}>{isExpanded ? '▲ Hide Details' : '▼ Audit Verification'}</span>
                    </div>
                  </div>

                  {isExpanded && (
                    <div style={{marginTop:'14px', paddingTop:'14px', borderTop:'1px dashed var(--border)'}}>
                      {/* Live Cryptographic Fingerprint Verification Card */}
                      {liveAudit && (
                        <div style={{marginBottom:'14px', padding:'14px', borderRadius:'12px', background: isLiveTampered ? 'rgba(239,68,68,0.08)' : 'var(--bg1)', border: isLiveTampered ? '1px solid rgba(239,68,68,0.3)' : '1px solid var(--border)'}}>
                          <div style={{display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:'8px'}}>
                            <div style={{fontWeight:700, fontSize:'13px', color:'var(--text)'}}>
                              {isLiveTampered ? `🔴 Live Graph Database Tampering Flagged (${(liveAudit.tampered_document_types || []).join(', ') || 'Graph Mismatch'})` : '🟢 Live Neo4j Graph Integrity Proof'}
                            </div>
                            <span className="mono" style={{fontSize:'11px', color:'var(--text-faint)'}}>{liveAudit.verification_timestamp}</span>
                          </div>
                          <div className="cards-grid" style={{gridTemplateColumns:'repeat(auto-fit, minmax(240px, 1fr))', gap:'10px', marginBottom:0}}>
                            <div>
                              <div style={{fontSize:'11px', color:'var(--text-faint)', marginBottom:'2px'}}>On-Chain Recorded Merkle Root:</div>
                              <div className="mono" style={{fontSize:'10.5px', color:'var(--accent)', wordBreak:'break-all', background:'var(--surface)', padding:'6px', borderRadius:'6px', border:'1px solid var(--border)'}}>
                                {esc(liveAudit.merkle_root)}
                              </div>
                            </div>
                            <div>
                              <div style={{fontSize:'11px', color:'var(--text-faint)', marginBottom:'2px'}}>Live Graph Fingerprint Hash:</div>
                              <div className="mono" style={{fontSize:'10.5px', color: isLiveTampered ? '#ef4444' : '#10b981', wordBreak:'break-all', background:'var(--surface)', padding:'6px', borderRadius:'6px', border: isLiveTampered ? '1px solid rgba(239,68,68,0.4)' : '1px solid var(--border)'}}>
                                {esc(liveAudit.graph_fingerprint)}
                              </div>
                            </div>
                          </div>
                          {isLiveTampered && (
                            <div style={{marginTop:'10px', fontSize:'12px', color:'#ef4444', fontWeight:600, display:'flex', alignItems:'center', gap:'6px'}}>
                              <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><path d="M12 9v4"/><path d="M12 17h.01"/></svg>
                              Document Tampering Detected: Live Neo4j records in domain {(liveAudit.tampered_document_types || []).map(t => `'${t}'`).join(', ')} contain modified database fields.
                            </div>
                          )}
                        </div>
                      )}

                      <div style={{fontWeight:700, fontSize:'13px', marginBottom:'10px', color:'var(--text-dim)'}}>Associated Document Evidence Blocks ({caseBlocks.length}):</div>
                      <div className="cards-grid" style={{gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))'}}>
                        {caseBlocks.length ? caseBlocks.map(b => {
                          const isTypeTampered = liveAudit && (liveAudit.tampered_document_types || []).includes(b.document_type);
                          const isBlockValid = b.is_valid !== false;
                          const isValid = isBlockValid && !isTypeTampered;
                          const icon = docIconMap[b.document_type] || '📁';
                          return (
                            <div key={b.document_id || b.index} className="card" style={{marginBottom:0, background:'var(--surface-hover)', border: isValid ? '1px solid var(--border)' : '1px solid rgba(239,68,68,0.4)'}}>
                              <div style={{display:'flex', alignItems:'center', justifyContent:'space-between', gap:'8px', marginBottom:'10px'}}>
                                <span style={{fontSize:'22px'}}>{icon}</span>
                                {isValid ? (
                                  <span className="tag low">VERIFIED</span>
                                ) : (
                                  <span className="tag crit" style={{background:'rgba(239,68,68,0.2)', color:'#ef4444', border:'1px solid rgba(239,68,68,0.4)', fontWeight:700}}>
                                    🔴 {!isBlockValid ? 'BLOCK TAMPERED' : `${b.document_type} DB TAMPERED`}
                                  </span>
                                )}
                              </div>
                              <div style={{fontWeight:700, fontSize:'14px', color:'var(--text)', marginBottom:'4px'}}>{esc(b.document_name || b.document_type)}</div>
                              <div className="mono" style={{fontSize:'11px', color:'var(--text-faint)', marginBottom:'10px'}}>ID: {esc(b.document_id)} · Block #{b.index}</div>
                              <div style={{fontSize:'11px', color:'var(--text-dim)', marginBottom:'4px'}}>Evidence Payload Hash:</div>
                              <div className="mono" style={{fontSize:'10.5px', color: isValid ? 'var(--accent)' : '#ef4444', wordBreak:'break-all', background:'var(--bg1)', padding:'6px', borderRadius:'6px', border:'1px solid var(--border)'}}>
                                {esc(b.evidence_hash)}
                              </div>
                              <div style={{fontSize:'11px', color:'var(--text-faint)', marginTop:'8px', textAlign:'right'}}>{esc(b.formatted_time)}</div>
                            </div>
                          );
                        }) : (
                          <div className="empty" style={{gridColumn:'1/-1'}}>No document evidence blocks logged yet for this case.</div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      <div className="card">
        <div className="card-header">
          <div className="card-title">Immutable Block History Ledger</div>
          <span className="tag plain">{blocks.length} Blocks</span>
        </div>
        <div className="tbl-wrap">
          <table>
            <thead>
              <tr>
                <th>Block #</th>
                <th>Case ID</th>
                <th>Document Name / Type</th>
                <th>Timestamp</th>
                <th>Evidence Hash (SHA-256)</th>
                <th>Merkle Root</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {blocks.filter(b => b.case_id !== 'SYSTEM_GENESIS' && b.document_type !== 'SYSTEM_GENESIS').map(b => {
                const isValid = b.is_valid !== false;
                return (
                  <tr key={b.index} style={!isValid ? {background:'rgba(239,68,68,0.06)'} : {}}>
                    <td className="mono"><b>#{b.index}</b></td>
                    <td><span className="tag open mono" style={{cursor:'pointer'}} onClick={() => toggleCaseExpand(b.case_id)}>{esc(b.case_id)}</span></td>
                    <td><b>{esc(b.document_name || b.document_type || 'CASE_MASTER')}</b> <span className="mono" style={{fontSize:'11px', color:'var(--text-faint)'}}>({esc(b.document_type)})</span></td>
                    <td style={{fontSize:'12px', color:'var(--text-dim)'}}>{esc(b.formatted_time)}</td>
                    <td className="mono" style={{fontSize:'11px'}} title={esc(b.evidence_hash)}>{esc(b.evidence_hash?.substring(0, 16))}…</td>
                    <td className="mono" style={{fontSize:'11px'}} title={esc(b.merkle_root)}>{esc(b.merkle_root?.substring(0, 16))}…</td>
                    <td>{isValid ? <span className="tag low">VERIFIED</span> : <span className="tag crit" style={{background:'rgba(239,68,68,0.2)', color:'#ef4444', border:'1px solid rgba(239,68,68,0.4)', fontWeight:700}}>TAMPERED</span>}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
