import React, { useState, useEffect } from 'react';
import { API, esc, LABEL_COLOR, Entity, removeOfficerUploadedCaseId } from '../services/api';
import { LocalCaseStore } from '../services/fileStore';
import { FormattedAiMessage, renderInlineMarkdown } from './FormattedAiMessage';
import { EntityPropertiesTable } from './EntityPropertiesTable';

export interface EntityConnection {
  target_id?: string;
  target_name?: string;
  rel_type?: string;
  neighbor_id?: string;
  neighbor_name?: string;
  relationship?: string;
  direction?: string;
  [key: string]: unknown;
}

export interface EntityModalData extends Entity {
  node?: Entity & { display_name?: string; entity_id?: string };
  connections?: EntityConnection[];
  display_name?: string;
  entity_id?: string;
}

export interface EntityModalContentProps {
  data: Entity;
  onClose: () => void;
  openEntityModal: (id: string) => void;
}

export function EntityModalContent({ data, onClose, openEntityModal }: EntityModalContentProps) {
  if (!data) return null;
  const d = data as EntityModalData;
  const node = (d.node || d) as Entity & { display_name?: string; entity_id?: string };
  const rawConnections: EntityConnection[] = (d.connections || []) as EntityConnection[];
  const seenKeys = new Set<string>();
  const connections: EntityConnection[] = [];
  for (const c of rawConnections) {
    const relType = (c.rel_type || c.relationship || 'CONNECTED') as string;
    if (['CHAINED_TO', 'PREVIOUS_BLOCK'].includes(relType)) continue;
    const targetId = (c.target_id || c.neighbor_id || '') as string;
    const dirArrow = c.direction === 'INCOMING' ? '←' : '→';
    const key = `${relType}_${dirArrow}_${targetId}`;
    if (seenKeys.has(key)) continue;
    seenKeys.add(key);
    connections.push(c);
  }

  const propsDict = (node.properties as Record<string, unknown>) || node;
  const displayName = node.name || node.display_name || propsDict.name || propsDict.display_name || propsDict.handle || propsDict.phone_number || propsDict.account_number || node.id || node.entity_id;
  const entityId = node.id || node.entity_id || propsDict.person_id || propsDict.phone_number || propsDict.account_number || propsDict.handle_id || '';

  const isPhone = (node.labels || []).includes('Phone') || propsDict.phone_number !== undefined;
  let associatedPerson = (propsDict.associated_person_name || propsDict.registered_owner || propsDict.subscriber_name || propsDict.owner_name) as string | undefined;
  let associatedPersonId = (propsDict.associated_person_id || propsDict.owner_person_id) as string | undefined;

  if (isPhone && !associatedPerson) {
    const ownerConn = connections.find(c => {
      const rel = (c.rel_type || c.relationship || '').toUpperCase();
      const isRel = ['OWNS', 'USES', 'HAS_PHONE', 'SUBSCRIBER'].includes(rel);
      const isPersonNeighbor = Array.isArray(c.neighbor_labels) && c.neighbor_labels.includes('Person');
      return isRel || isPersonNeighbor;
    });
    if (ownerConn) {
      associatedPerson = (ownerConn.target_name || ownerConn.neighbor_name || ownerConn.target_id) as string;
      associatedPersonId = (ownerConn.target_id || ownerConn.neighbor_id) as string;
    }
  }

  const cleanAssociatedPerson = associatedPerson ? String(associatedPerson).split('\n')[0].replace(/^\(|\)$/g, '').trim() : '';

  return (
    <div>
      <button className="neu-btn ghost transition hover:opacity-80" onClick={onClose} style={{ float: 'right' }}>✕</button>
      <div className="flex items-center gap-3 mb-3.5" style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '14px' }}>
        <span className="dot" style={{ width: '16px', height: '16px', background: LABEL_COLOR[node.labels?.[0] || ''] || '#94a3b8', borderRadius: '50%' }}></span>
        <div>
          <h3 className="font-semibold text-base" style={{ margin: 0 }}>{esc(displayName)}</h3>
          <div className="mono text-xs" style={{ fontSize: '12px', color: 'var(--text-faint)' }}>ID: {esc(entityId)}</div>
        </div>
      </div>

      {isPhone && cleanAssociatedPerson && cleanAssociatedPerson.toLowerCase() !== 'unknown' && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '12px 14px',
            borderRadius: '8px',
            background: 'rgba(59, 130, 246, 0.1)',
            border: '1px solid rgba(59, 130, 246, 0.25)',
            marginBottom: '18px',
            flexWrap: 'wrap',
            gap: '10px'
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div style={{ width: '34px', height: '34px', borderRadius: '50%', background: 'rgba(59, 130, 246, 0.2)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '18px' }}>
              👤
            </div>
            <div>
              <div style={{ fontSize: '11px', color: 'var(--text-faint)', textTransform: 'uppercase', fontWeight: 650, letterSpacing: '0.04em' }}>
                Associated Person / Subscriber
              </div>
              <div style={{ fontSize: '15px', fontWeight: 700, color: 'var(--text)' }}>
                {esc(cleanAssociatedPerson)}
              </div>
              {associatedPersonId && (
                <div className="mono" style={{ fontSize: '11px', color: 'var(--text-dim)' }}>
                  Person ID: {esc(associatedPersonId)}
                </div>
              )}
            </div>
          </div>
          {associatedPersonId && (
            <button
              className="neu-btn primary transition hover:opacity-90"
              style={{ fontSize: '12px', padding: '5px 12px' }}
              onClick={() => {
                onClose();
                openEntityModal(String(associatedPersonId));
              }}
            >
              View Person ➔
            </button>
          )}
        </div>
      )}

      <EntityPropertiesTable properties={propsDict} labels={node.labels} />

      {/* Call & Communication Breakdown if available */}
      {Boolean(propsDict.communications && typeof propsDict.communications === 'object' && Object.keys(propsDict.communications).length > 0) && (
        <div style={{ marginBottom: '20px', padding: '12px 14px', borderRadius: '10px', background: 'var(--surface-hover)', border: '1px solid var(--border)' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' }}>
            <div style={{ fontWeight: 700, fontSize: '13px', display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--accent)' }}>
              <span>📞</span> Call & Telecommunication Breakdown
            </div>
            {propsDict.total_calls !== undefined && (
              <span className="tag plain" style={{ fontWeight: 700, fontSize: '11px', color: 'var(--accent)' }}>
                Total: {String(propsDict.total_calls)} calls
              </span>
            )}
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', maxHeight: '160px', overflowY: 'auto' }}>
            {Object.values((propsDict.communications || {}) as Record<string, any>).map((comm: any, cIdx: number) => (
              <div
                key={cIdx}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '6px 10px',
                  borderRadius: '6px',
                  background: 'var(--card-bg)',
                  border: '1px solid var(--border)',
                  fontSize: '12px'
                }}
              >
                <div>
                  <span style={{ fontWeight: 600 }}>{comm.partner_name || comm.partner_id}</span>
                  <span className="mono" style={{ color: 'var(--text-dim)', marginLeft: '6px', fontSize: '11px' }}>({comm.partner_id})</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ fontWeight: 700, color: 'var(--accent)' }}>📞 {comm.call_count} {comm.call_count === 1 ? 'call' : 'calls'}</span>
                  {comm.summary && <span style={{ color: 'var(--text-dim)', fontSize: '11px' }}>({comm.summary})</span>}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Financial Transactions Breakdown if available */}
      {Boolean(propsDict.transactions && typeof propsDict.transactions === 'object' && Object.keys(propsDict.transactions).length > 0) && (
        <div style={{ marginBottom: '20px', padding: '12px 14px', borderRadius: '10px', background: 'var(--surface-hover)', border: '1px solid var(--border)' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' }}>
            <div style={{ fontWeight: 700, fontSize: '13px', display: 'flex', alignItems: 'center', gap: '6px', color: '#10b981' }}>
              <span>💳</span> Financial Transactions & Fund Flow Breakdown
            </div>
            {propsDict.total_transactions !== undefined && (
              <span className="tag plain" style={{ fontWeight: 700, fontSize: '11px', color: '#10b981' }}>
                Total: {String(propsDict.total_transactions)} txns
                {propsDict.total_amount_transferred !== undefined ? ` (₹${Math.round(Number(propsDict.total_amount_transferred)).toLocaleString()})` : ''}
              </span>
            )}
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', maxHeight: '160px', overflowY: 'auto' }}>
            {Object.values((propsDict.transactions || {}) as Record<string, any>).map((tx: any, tIdx: number) => (
              <div
                key={tIdx}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '6px 10px',
                  borderRadius: '6px',
                  background: 'var(--card-bg)',
                  border: '1px solid var(--border)',
                  fontSize: '12px'
                }}
              >
                <div>
                  <span style={{ fontWeight: 600 }}>{tx.partner_name || tx.partner_id}</span>
                  <span className="mono" style={{ color: 'var(--text-dim)', marginLeft: '6px', fontSize: '11px' }}>({tx.partner_id})</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ fontWeight: 700, color: '#10b981' }}>💳 {tx.tx_count} {tx.tx_count === 1 ? 'txn' : 'txns'}</span>
                  {tx.summary && <span style={{ color: 'var(--text-dim)', fontSize: '11px' }}>({tx.summary})</span>}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {connections.length > 0 && (
        <div>
          <div className="font-bold text-sm mb-2.5" style={{ fontWeight: 700, fontSize: '14px', marginBottom: '10px' }}>Direct Connections ({connections.length}):</div>
          <div style={{ maxHeight: '240px', overflowY: 'auto', border: '1px solid var(--border)', borderRadius: '10px' }}>
            {connections.map((c, idx) => {
              const targetId = (c.target_id || c.neighbor_id || '') as string;
              const targetName = (c.target_name || c.neighbor_name || targetId) as string;
              const relType = (c.rel_type || c.relationship || 'CONNECTED') as string;
              const dirArrow = c.direction === 'INCOMING' ? '←' : '→';
              const relProps = (c.relationship_properties || c.properties || {}) as any;
              const callCount = relProps.call_count;
              const txCount = relProps.tx_count;
              const summary = relProps.summary;
              const isFinance = relType.includes('TRANSFERRED') || relType.includes('TRANSACTION') || relType.includes('FUNDS');

              return (
                <div
                  key={idx}
                  className="list-row flex items-center justify-between transition hover:bg-surface-hover"
                  style={{ cursor: 'pointer', padding: '10px 14px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}
                  onClick={() => { onClose(); openEntityModal(targetId); }}
                >
                  <div>
                    <div className="l-name font-medium" style={{ fontWeight: 600, fontSize: '13.5px' }}>{esc(targetName)}</div>
                    <div className="l-sub mono text-xs" style={{ fontSize: '12px', color: 'var(--text-dim)', marginTop: '2px', display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
                      <span style={{ color: isFinance ? '#10b981' : 'var(--accent)' }}>{esc(relType)}</span>
                      {dirArrow}
                      <span style={{ opacity: 0.8 }}>{esc(targetId)}</span>
                      {(callCount && callCount > 1) ? (
                        <span style={{ padding: '1px 6px', borderRadius: '10px', background: 'rgba(0, 210, 255, 0.15)', color: 'var(--accent)', fontWeight: 700, fontSize: '11px' }}>
                          📞 {summary || `${callCount} calls`}
                        </span>
                      ) : (txCount && txCount > 1) ? (
                        <span style={{ padding: '1px 6px', borderRadius: '10px', background: 'rgba(16, 185, 129, 0.15)', color: '#10b981', fontWeight: 700, fontSize: '11px' }}>
                          💳 {summary || `${txCount} txns`}
                        </span>
                      ) : summary ? (
                        <span style={{ padding: '1px 6px', borderRadius: '10px', background: isFinance ? 'rgba(16, 185, 129, 0.15)' : 'rgba(0, 210, 255, 0.15)', color: isFinance ? '#10b981' : 'var(--accent)', fontWeight: 600, fontSize: '11px' }}>
                          {summary}
                        </span>
                      ) : null}
                    </div>
                  </div>
                  <button className="neu-btn ghost text-xs" style={{ fontSize: '11px', padding: '4px 10px' }}>INSPECT</button>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

export interface AiDossierModalContentProps {
  caseId: string;
  caseName: string;
  onClose: () => void;
}

interface AiDossierData {
  title?: string;
  executive_summary?: string;
  summary?: string;
  key_findings?: string[];
  error?: string;
  [key: string]: unknown;
}

export function AiDossierModalContent({ caseId, caseName, onClose }: AiDossierModalContentProps) {
  const [dossier, setDossier] = useState<AiDossierData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    let isMounted = true;
    async function generate() {
      try {
        const res = await API.get<AiDossierData>(`/api/cases/${encodeURIComponent(caseId)}/ai-dossier`);
        if (isMounted) setDossier(res);
      } catch (e: any) {
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
      <button className="neu-btn ghost transition hover:opacity-80" onClick={onClose} style={{ float: 'right' }}>✕</button>
      <div className="flex items-center gap-2.5 mb-3.5" style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '14px' }}>
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth="2"><path d="m12 3-1.9 5.8a2 2 0 0 1-1.3 1.3L3 12l5.8 1.9a2 2 0 0 1 1.3 1.3L12 21l1.9-5.8a2 2 0 0 1 1.3-1.3L21 12l-5.8-1.9a2 2 0 0 1-1.3-1.3Z"/></svg>
        <h3 className="m-0 font-semibold" style={{ margin: 0 }}>AI Executive Case Dossier</h3>
      </div>
      <div className="mono text-xs mb-4.5" style={{ fontSize: '12px', color: 'var(--text-faint)', marginBottom: '18px' }}>
        Case: {esc(caseName)} ({esc(caseId)})
      </div>

      {loading ? (
        <div style={{ padding: '40px 20px', textAlign: 'center' }}>
          <div className="status-dot" style={{ width: '14px', height: '14px', background: 'var(--accent)', animation: 'pulse 1s infinite', margin: '0 auto 12px' }}></div>
          <div className="font-semibold text-sm" style={{ fontWeight: 600, fontSize: '14px' }}>Synthesizing Executive Case Intelligence…</div>
          <div className="text-xs mt-1" style={{ fontSize: '12px', color: 'var(--text-faint)', marginTop: '4px' }}>Running graph inference & threat correlation</div>
        </div>
      ) : dossier?.error ? (
        <div className="empty" style={{ color: 'var(--red)' }}>Failed to generate dossier: {dossier.error}</div>
      ) : (
        <div style={{ lineHeight: 1.6, fontSize: '14px', color: 'var(--text)' }}>
          <div className="font-bold mb-2" style={{ fontWeight: 700, fontSize: '15px', color: 'var(--accent)', marginBottom: '8px' }}>
            {esc(dossier?.title || 'Executive Dossier')}
          </div>
          <div className="mb-4" style={{ marginBottom: '16px', background: 'var(--bg1)', padding: '14px', borderRadius: '10px', border: '1px solid var(--border)' }}>
            <FormattedAiMessage content={dossier?.executive_summary || dossier?.summary || 'Summary generated from Neo4j knowledge graph topology.'} />
          </div>
          {(dossier?.key_findings || []).length > 0 && (
            <div className="mb-4" style={{ marginBottom: '16px' }}>
              <div className="font-bold mb-1.5" style={{ fontWeight: 700, fontSize: '13.5px', marginBottom: '6px' }}>Key Investigative Findings:</div>
              {(dossier?.key_findings || []).map((f, i) => (
                <div key={i} className="flex gap-2 mb-1 text-sm" style={{ fontSize: '13px', color: 'var(--text-dim)', marginBottom: '4px', display: 'flex', gap: '8px' }}>
                  <span style={{ color: 'var(--accent)' }}>•</span>
                  <div>{renderInlineMarkdown(esc(f))}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export interface ResetDbConfirmContentProps {
  onClose: () => void;
  addToast: (msg: string, type?: string) => void;
  onSuccess: () => void;
}

export function ResetDbConfirmContent({ onClose, addToast, onSuccess }: ResetDbConfirmContentProps) {
  const [resetting, setResetting] = useState<boolean>(false);

  const handleReset = async () => {
    setResetting(true);
    try {
      await API.delete('/api/cases/reset?confirm=true');
      addToast('Database reset successfully!', 'ok');
      onSuccess();
      onClose();
    } catch (e: any) {
      addToast(`Reset failed: ${e.message}`, 'err');
    } finally {
      setResetting(false);
    }
  };

  return (
    <div className="confirm-box">
      <div className="confirm-header flex items-center gap-2">
        <svg viewBox="0 0 24 24" fill="none" strokeWidth="2"><path d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/></svg>
        <div className="confirm-title font-semibold">Reset Complete Knowledge Graph?</div>
      </div>
      <div className="confirm-body text-sm leading-relaxed">
        This action will <b>permanently delete all cases, people, phones, bank accounts, transactions, and relationships</b> from the Neo4j database. This operation cannot be undone.
      </div>
      <div className={`confirm-actions flex justify-end gap-3`}>
        <button className="neu-btn ghost transition" onClick={onClose} disabled={resetting}>Cancel</button>
        <button className="neu-btn danger transition" onClick={handleReset} disabled={resetting}>{resetting ? 'Resetting…' : 'Yes, Reset Database'}</button>
      </div>
    </div>
  );
}

export interface DeleteCaseConfirmContentProps {
  caseId: string;
  caseName?: string;
  onClose: () => void;
  addToast: (msg: string, type?: string) => void;
  onSuccess: () => void;
  officerBadge?: string;
}

export function DeleteCaseConfirmContent({ caseId, caseName, onClose, addToast, onSuccess, officerBadge }: DeleteCaseConfirmContentProps) {
  const [deleting, setDeleting] = useState<boolean>(false);

  const handleDelete = async () => {
    setDeleting(true);
    try {
      try {
        await API.delete(`/api/cases/${encodeURIComponent(caseId)}?confirm=true`);
      } catch (e: any) {
        console.warn('Backend case deletion note:', e.message);
      }

      // Purge from local persistent store
      LocalCaseStore.deleteCase(caseId);

      // Remove from officer session link
      if (officerBadge) {
        removeOfficerUploadedCaseId(officerBadge, caseId);
      }

      addToast(`Case '${caseId}' deleted successfully!`, 'ok');
      onSuccess();
      onClose();
    } catch (e: any) {
      addToast(`Deletion failed: ${e.message}`, 'err');
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div style={{ maxWidth: '440px', margin: '0 auto', textAlign: 'center', padding: '10px 4px' }}>
      <div
        style={{
          width: '52px',
          height: '52px',
          borderRadius: '50%',
          background: 'rgba(239, 68, 68, 0.12)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          margin: '0 auto 16px'
        }}
      >
        <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="#ef4444" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
        </svg>
      </div>

      <h3 style={{ fontSize: '18px', fontWeight: 700, color: 'var(--text)', margin: '0 0 10px', lineHeight: 1.3 }}>
        Delete Case '{esc(caseName || caseId)}'?
      </h3>

      <p style={{ fontSize: '13.5px', color: 'var(--text-dim)', lineHeight: 1.55, margin: '0 0 22px' }}>
        Are you sure you want to delete Case <strong className="mono" style={{ color: 'var(--accent)' }}>{esc(caseId)}</strong>? Exclusive nodes and evidence records belonging to this case will be purged from the database.
      </p>

      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
        <button
          className="neu-btn ghost transition"
          onClick={onClose}
          disabled={deleting}
          style={{ padding: '8px 18px', fontSize: '13px' }}
        >
          Cancel
        </button>
        <button
          className="neu-btn danger font-semibold transition"
          onClick={handleDelete}
          disabled={deleting}
          style={{ padding: '8px 20px', fontSize: '13px' }}
        >
          {deleting ? 'Deleting…' : 'Delete Case'}
        </button>
      </div>
    </div>
  );
}

export interface CaseAlreadyExistsModalProps {
  caseId: string;
  caseName?: string;
  status?: string;
  onClose: () => void;
  onViewCase?: (caseId: string) => void;
}

export function CaseAlreadyExistsModal({ caseId, caseName, status, onClose, onViewCase }: CaseAlreadyExistsModalProps) {
  return (
    <div className="modal-overlay open" style={{ zIndex: 10000 }}>
      <div className="modal" style={{ maxWidth: '480px', textAlign: 'center', padding: '32px 28px' }}>
        <div style={{
          width: '56px',
          height: '56px',
          borderRadius: '50%',
          background: 'rgba(239, 68, 68, 0.15)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          margin: '0 auto 16px'
        }}>
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#ef4444" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>
            <line x1="12" y1="9" x2="12" y2="13"></line>
            <line x1="12" y1="17" x2="12.01" y2="17"></line>
          </svg>
        </div>

        <h3 className="font-bold text-lg mb-2" style={{ color: 'var(--text)', fontSize: '18px', margin: '0 0 8px' }}>
          Case is Already Uploaded
        </h3>

        <p style={{ fontSize: '13.5px', color: 'var(--text-dim)', lineHeight: 1.5, margin: '0 0 18px' }}>
          The case record <span className="mono font-bold" style={{ color: 'var(--accent)' }}>{esc(caseId)}</span> {caseName ? `("${esc(caseName)}")` : ''} already exists in the intelligence database.
        </p>

        <div style={{
          background: 'var(--bg1)',
          border: '1px solid var(--border)',
          borderRadius: '8px',
          padding: '12px 14px',
          fontSize: '12.5px',
          marginBottom: '22px',
          textAlign: 'left',
          lineHeight: 1.5
        }}>
          <div style={{ color: 'var(--text)', marginBottom: '4px' }}>
            <span style={{ color: 'var(--text-faint)', fontWeight: 600 }}>STATUS: </span>
            <span className="mono font-semibold" style={{ color: 'var(--accent)' }}>{esc(status || 'ACTIVE IN GRAPH')}</span>
          </div>
          <div style={{ color: 'var(--text-dim)' }}>
            To add new evidence, CDR call logs, or addendums to this existing case, use the <b>"Attach Document"</b> option in the Case Registry.
          </div>
        </div>

        <div className="flex justify-end gap-2.5" style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
          <button className="neu-btn ghost" onClick={onClose} style={{ padding: '8px 16px' }}>
            Close
          </button>
          {onViewCase && (
            <button className="neu-btn primary" onClick={() => { onClose(); onViewCase(caseId); }} style={{ padding: '8px 18px' }}>
              View Existing Case
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
