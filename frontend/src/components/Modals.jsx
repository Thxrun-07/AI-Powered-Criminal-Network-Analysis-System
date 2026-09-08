import React, { useState, useEffect } from 'react';
import { API, esc, LABEL_COLOR } from '../services/api.js';

export function EntityModalContent({ data, onClose, openEntityModal }) {
  if (!data) return null;
  const node = data.node || data;
  const connections = data.connections || [];

  return (
    <div>
      <button className="neu-btn ghost" onClick={onClose} style={{float:'right'}}>✕</button>
      <div style={{display:'flex', alignItems:'center', gap:'12px', marginBottom:'14px'}}>
        <span className="dot" style={{width:'16px', height:'16px', background: LABEL_COLOR[node.labels?.[0]] || '#94a3b8', borderRadius:'50%'}}></span>
        <div>
          <h3>{esc(node.name || node.display_name || node.id)}</h3>
          <div className="mono" style={{fontSize:'12px', color:'var(--text-faint)'}}>ID: {esc(node.id || node.entity_id)}</div>
        </div>
      </div>

      <div className="kv" style={{marginBottom:'20px'}}>
        {Object.entries(node.properties || node)
          .filter(([k]) => !['properties', 'labels', 'node', 'connections'].includes(k))
          .map(([k, v]) => (
            <div key={k}>
              <div className="k">{esc(k)}</div>
              <div className="v mono">{esc(typeof v === 'object' ? JSON.stringify(v) : v)}</div>
            </div>
          ))}
      </div>

      {connections.length > 0 && (
        <div>
          <div style={{fontWeight:700, fontSize:'14px', marginBottom:'10px'}}>Direct Connections ({connections.length}):</div>
          <div style={{maxHeight:'240px', overflowY:'auto', border:'1px solid var(--border)', borderRadius:'10px'}}>
            {connections.map((c, idx) => (
              <div key={idx} className="list-row" style={{cursor:'pointer'}} onClick={() => { onClose(); openEntityModal(c.target_id); }}>
                <div>
                  <div className="l-name">{esc(c.target_name || c.target_id)}</div>
                  <div className="l-sub mono">{esc(c.rel_type)} → {esc(c.target_id)}</div>
                </div>
                <span className="tag plain">Inspect</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export function AiDossierModalContent({ caseId, caseName, onClose }) {
  const [dossier, setDossier] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let isMounted = true;
    async function generate() {
      try {
        const res = await API.get(`/api/cases/${encodeURIComponent(caseId)}/ai-dossier`);
        if (isMounted) setDossier(res);
      } catch (e) {
        if (isMounted) setDossier({ error: e.message });
      } finally {
        if (isMounted) setLoading(false);
      }
    }
    generate();
    return () => { isMounted = false; };
  }, [caseId]);

  return (
    <div>
      <button className="neu-btn ghost" onClick={onClose} style={{float:'right'}}>✕</button>
      <div style={{display:'flex', alignItems:'center', gap:'10px', marginBottom:'14px'}}>
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth="2"><path d="m12 3-1.9 5.8a2 2 0 0 1-1.3 1.3L3 12l5.8 1.9a2 2 0 0 1 1.3 1.3L12 21l1.9-5.8a2 2 0 0 1 1.3-1.3L21 12l-5.8-1.9a2 2 0 0 1-1.3-1.3Z"/></svg>
        <h3 style={{margin:0}}>AI Executive Case Dossier</h3>
      </div>
      <div className="mono" style={{fontSize:'12px', color:'var(--text-faint)', marginBottom:'18px'}}>
        Case: {esc(caseName)} ({esc(caseId)})
      </div>

      {loading ? (
        <div style={{padding:'40px 20px', textAlign:'center'}}>
          <div className="status-dot" style={{width:'14px', height:'14px', background:'var(--accent)', animation:'pulse 1s infinite', margin:'0 auto 12px'}}></div>
          <div style={{fontWeight:600, fontSize:'14px'}}>Synthesizing Executive Case Intelligence…</div>
          <div style={{fontSize:'12px', color:'var(--text-faint)', marginTop:'4px'}}>Running graph inference & threat correlation</div>
        </div>
      ) : dossier?.error ? (
        <div className="empty" style={{color:'var(--red)'}}>Failed to generate dossier: {dossier.error}</div>
      ) : (
        <div style={{lineHeight:1.6, fontSize:'14px', color:'var(--text)'}}>
          <div style={{fontWeight:700, fontSize:'15px', color:'var(--accent)', marginBottom:'8px'}}>
            {esc(dossier.title || 'Executive Dossier')}
          </div>
          <div style={{marginBottom:'16px', background:'var(--bg1)', padding:'14px', borderRadius:'10px', border:'1px solid var(--border)'}}>
            {esc(dossier.executive_summary || dossier.summary || 'Summary generated from Neo4j knowledge graph topology.')}
          </div>
          {(dossier.key_findings || []).length > 0 && (
            <div style={{marginBottom:'16px'}}>
              <div style={{fontWeight:700, fontSize:'13.5px', marginBottom:'6px'}}>Key Investigative Findings:</div>
              {dossier.key_findings.map((f, i) => (
                <div key={i} style={{fontSize:'13px', color:'var(--text-dim)', marginBottom:'4px', display:'flex', gap:'8px'}}>
                  <span style={{color:'var(--accent)'}}>•</span> {esc(f)}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function ResetDbConfirmContent({ onClose, addToast, onSuccess }) {
  const [resetting, setResetting] = useState(false);

  const handleReset = async () => {
    setResetting(true);
    try {
      await API.delete('/api/cases/reset-database', { confirm_reset: true });
      addToast('Database reset successfully!', 'ok');
      onSuccess();
      onClose();
    } catch (e) {
      addToast(`Reset failed: ${e.message}`, 'err');
    } finally {
      setResetting(false);
    }
  };

  return (
    <div className="confirm-box">
      <div className="confirm-header">
        <svg viewBox="0 0 24 24" fill="none" strokeWidth="2"><path d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/></svg>
        <div className="confirm-title">Reset Complete Knowledge Graph?</div>
      </div>
      <div className="confirm-body">
        This action will <b>permanently delete all cases, people, phones, bank accounts, transactions, and relationships</b> from the Neo4j database. This operation cannot be undone.
      </div>
      <div className="confirm-actions">
        <button className="neu-btn ghost" onClick={onClose} disabled={resetting}>Cancel</button>
        <button className="neu-btn danger" onClick={handleReset} disabled={resetting}>{resetting ? 'Resetting…' : 'Yes, Reset Database'}</button>
      </div>
    </div>
  );
}

export function DeleteCaseConfirmContent({ caseId, caseName, onClose, addToast, onSuccess }) {
  const [deleting, setDeleting] = useState(false);

  const handleDelete = async () => {
    setDeleting(true);
    try {
      await API.delete(`/api/cases/${encodeURIComponent(caseId)}`);
      addToast(`Case '${caseId}' deleted successfully!`, 'ok');
      onSuccess();
      onClose();
    } catch (e) {
      addToast(`Deletion failed: ${e.message}`, 'err');
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div className="confirm-box">
      <div className="confirm-header">
        <svg viewBox="0 0 24 24" fill="none" strokeWidth="2"><path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
        <div className="confirm-title">Delete Case '{esc(caseName || caseId)}'?</div>
      </div>
      <div className="confirm-body">
        Are you sure you want to delete Case <b>{esc(caseId)}</b>? Exclusive nodes and relationships belonging to this case will be purged from Neo4j. Multi-case entities will be retained.
      </div>
      <div className="confirm-actions">
        <button className="neu-btn ghost" onClick={onClose} disabled={deleting}>Cancel</button>
        <button className="neu-btn danger" onClick={handleDelete} disabled={deleting}>{deleting ? 'Deleting…' : 'Delete Case'}</button>
      </div>
    </div>
  );
}
