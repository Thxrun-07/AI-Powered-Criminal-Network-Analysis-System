import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import * as vis from 'vis-network/standalone';
import { API, esc, LABEL_COLOR, getDeterministicSeed, Case, ThemeMode } from '../services/api';
import { CaseAlreadyExistsModal } from './Modals';

export interface OverlappingCase {
  case_id: string;
  case_name?: string;
  shared_count?: number;
  sample_entities?: string[];
}

export interface CaseOverlap {
  has_overlap?: boolean;
  overlap_count?: number;
  overlapping_cases: OverlappingCase[];
}

export interface SuspectOrVictim {
  name: string;
  roles?: string | string[];
}

export interface EvidenceItem {
  icon?: string;
  name: string;
}

declare module '../services/api' {
  interface Case {
    case_type?: string;
    priority?: string;
    date?: string;
    category_of_crime?: string;
    lead_investigator?: string;
    created_at?: string;
    summary?: string;
    case_overlap?: CaseOverlap;
    primary_suspects?: SuspectOrVictim[];
    victims?: SuspectOrVictim[];
    evidences_collected?: EvidenceItem[];
  }
}

export interface CaseRegistryModuleProps {
  cases: Case[];
  fetchCases: () => Promise<Case[]>;
  selectedCase: string | null;
  setSelectedCase: (id: string | null) => void;
  openAiDossier: (caseId: string, caseName: string) => void;
  promptDeleteCase: (caseId: string, caseName: string) => void;
  changeView: (view: string) => void;
  theme: string;
  addToast: (msg: string, type?: string) => void;
}

const sampleJson = {
  "case_metadata": {
    "case_id": "CASE-2026-999",
    "case_name": "Operation Cyber Vault",
    "case_type": "CYBER_FRAUD",
    "priority": "HIGH",
    "status": "OPEN",
    "summary": "Extortion ring operating via spoofed banking portals and cryptowallet laundering."
  },
  "entities": {
    "people": [{ "id": "P-999", "name": "Vikram Malhotra", "status": "Suspect", "age": 34 }],
    "phones": [{ "msisdn": "+919876543210", "owner_id": "P-999", "carrier": "Airtel" }],
    "bank_accounts": [{ "account_number": "ACC999888", "owner_id": "P-999", "bank_name": "HDFC Bank" }]
  },
  "relationships": {
    "communications": [{ "caller": "+919876543210", "callee": "+919999911111", "duration_seconds": 320, "type": "VOICE_CALL" }]
  }
};

export function CaseRegistryModule({
  cases,
  fetchCases,
  selectedCase,
  setSelectedCase,
  openAiDossier,
  promptDeleteCase,
  changeView,
  theme,
  addToast
}: CaseRegistryModuleProps) {
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [caseDetail, setCaseDetail] = useState<Case | null>(null);
  const [loadingDetail, setLoadingDetail] = useState<boolean>(false);

  // Ingest New Case Modal State
  const [isIngestModalOpen, setIsIngestModalOpen] = useState<boolean>(false);
  const [ingestTab, setIngestTab] = useState<'file' | 'json' | 'narrative'>('file');
  const [newCaseTitle, setNewCaseTitle] = useState<string>('');
  const [jsonText, setJsonText] = useState<string>('');
  const [ingestFiles, setIngestFiles] = useState<File[]>([]);
  const [narrativeText, setNarrativeText] = useState<string>('');
  const [ingesting, setIngesting] = useState<boolean>(false);
  const [alreadyExistsModal, setAlreadyExistsModal] = useState<{ caseId: string; caseName?: string; status?: string } | null>(null);

  // Attach File to Existing Case Modal State
  const [isAttachModalOpen, setIsAttachModalOpen] = useState<boolean>(false);
  const [attachTab, setAttachTab] = useState<'file' | 'narrative'>('file');
  const [attachFiles, setAttachFiles] = useState<File[]>([]);
  const [attachNarrative, setAttachNarrative] = useState<string>('');
  const [attaching, setAttaching] = useState<boolean>(false);

  const miniGraphRef = useRef<HTMLDivElement>(null);
  const miniNetworkInstanceRef = useRef<any>(null);

  const filteredCases = useMemo(() => {
    if (!statusFilter) return cases;
    return cases.filter(c => (c.status || '').toUpperCase() === statusFilter.toUpperCase());
  }, [cases, statusFilter]);

  const loadCaseDetail = useCallback(async (id: string) => {
    setSelectedCase(id);
    setLoadingDetail(true);
    try {
      const c = await API.get<Case>(`/api/cases/${encodeURIComponent(id)}`);
      setCaseDetail(c);
    } catch (e: any) {
      addToast(e.message, 'err');
      setCaseDetail(null);
    } finally {
      setLoadingDetail(false);
    }
  }, [setSelectedCase, addToast]);

  useEffect(() => {
    if (selectedCase) {
      loadCaseDetail(selectedCase);
    } else {
      setCaseDetail(null);
    }
  }, [selectedCase, loadCaseDetail]);

  useEffect(() => {
    if (!caseDetail || !miniGraphRef.current) return;
    let isMounted = true;
    async function renderMiniGraph() {
      try {
        const g = await API.get<{
          nodes?: Array<{ id: string; name?: string; labels?: string[] }>;
          edges?: Array<{ id?: string; source: string; target: string; type?: string }>;
        }>(`/api/graph?case_id=${encodeURIComponent(caseDetail!.case_id)}&limit=400`);
        if (!isMounted || !miniGraphRef.current) return;

        const isLight = theme === 'light';
        const seenNodeIds = new Set<string>();
        const nodes: Array<Record<string, unknown>> = [];
        (g.nodes || []).forEach(n => {
          if (n && n.id && !seenNodeIds.has(n.id)) {
            seenNodeIds.add(n.id);
            nodes.push({
              id: n.id, label: n.name || n.id, size: 12, shape: 'dot',
              color: { background: (n.labels?.[0] && LABEL_COLOR[n.labels[0]]) || '#94a3b8', border: isLight ? '#ffffff' : '#070a12' },
              font: { color: isLight ? '#0f172a' : '#cbd5e1', size: 11 }
            });
          }
        });

        const seenEdgeIds = new Set<string>();
        const edges: Array<Record<string, unknown>> = [];
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

        const seed = getDeterministicSeed(caseDetail!.case_id);
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

  // --- Handlers for New Case Ingestion ---
  const handleNewCaseJsonIngest = async () => {
    if (!newCaseTitle.trim()) { addToast('Case Title / Designation is required', 'info'); return; }
    if (!jsonText.trim()) { addToast('Please enter JSON payload', 'info'); return; }

    const targetTitle = newCaseTitle.trim();
    let targetCaseId = targetTitle;
    try {
      const parsedTest = JSON.parse(jsonText);
      if (parsedTest.case_metadata?.case_id) targetCaseId = parsedTest.case_metadata.case_id;
    } catch {}

    const existing = cases.find(c =>
      c.case_id.toLowerCase() === targetCaseId.toLowerCase() ||
      c.case_id.toLowerCase() === targetTitle.toLowerCase() ||
      (c.case_name && c.case_name.toLowerCase() === targetTitle.toLowerCase())
    );
    if (existing) {
      setAlreadyExistsModal({ caseId: existing.case_id, caseName: existing.case_name, status: existing.status });
      return;
    }

    setIngesting(true);
    try {
      const parsed = JSON.parse(jsonText);
      if (!parsed.case_metadata) parsed.case_metadata = {};
      if (!parsed.case_metadata.case_id) parsed.case_metadata.case_id = targetTitle;
      if (!parsed.case_metadata.case_name) parsed.case_metadata.case_name = targetTitle;

      const res = await API.post<{ case_id?: string; created?: { nodes?: number }; case_already_exists?: boolean }>('/api/v1/ingest/case', parsed);
      if (res.case_already_exists) {
        setAlreadyExistsModal({ caseId: res.case_id || targetTitle, caseName: targetTitle });
        await fetchCases();
        return;
      }
      addToast(`Successfully ingested Case '${res.case_id}'! Created ${res.created?.nodes || 0} nodes.`, 'ok');
      await fetchCases();
      setIsIngestModalOpen(false);
      setNewCaseTitle('');
      setJsonText('');
    } catch (e) {
      addToast(`Ingestion error: ${(e as Error).message}`, 'err');
    } finally {
      setIngesting(false);
    }
  };

  const handleNewCaseFileUpload = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!newCaseTitle.trim()) { addToast('Case Title / Designation is required', 'info'); return; }
    if (!ingestFiles || ingestFiles.length === 0) { addToast('Please select a file to upload', 'info'); return; }

    const targetTitle = newCaseTitle.trim();
    // 1. Check title against existing cases
    const existing = cases.find(c =>
      c.case_id.toLowerCase() === targetTitle.toLowerCase() ||
      (c.case_name && c.case_name.toLowerCase() === targetTitle.toLowerCase())
    );
    if (existing) {
      setAlreadyExistsModal({ caseId: existing.case_id, caseName: existing.case_name, status: existing.status });
      return;
    }

    // 2. Pre-inspect JSON files for embedded case_id
    for (const f of ingestFiles) {
      if (f.name.endsWith('.json')) {
        try {
          const text = await f.text();
          const d = JSON.parse(text);
          const cid = d.case_metadata?.case_id || d.case_id || (d.case_data && d.case_data.case_metadata?.case_id);
          if (cid) {
            const match = cases.find(c => c.case_id.toLowerCase() === cid.toLowerCase() || (c.case_name && c.case_name.toLowerCase() === cid.toLowerCase()));
            if (match) {
              setAlreadyExistsModal({ caseId: match.case_id, caseName: match.case_name, status: match.status });
              return;
            }
          }
        } catch {}
      }
    }

    setIngesting(true);
    try {
      const formData = new FormData();
      for (const f of ingestFiles) {
        formData.append('files', f);
        formData.append('file', f);
      }
      const url = `/api/v1/ingest?case_id=${encodeURIComponent(targetTitle)}`;
      const res = await API.send<{ case_id?: string; case_already_exists?: boolean }>(url, {
        method: 'POST',
        body: formData,
        form: true
      });
      if (res.case_already_exists) {
        setAlreadyExistsModal({ caseId: res.case_id || targetTitle, caseName: targetTitle });
        await fetchCases();
        return;
      }
      addToast(`File ingestion complete! Case ID: ${res.case_id}`, 'ok');
      await fetchCases();
      setIsIngestModalOpen(false);
      setNewCaseTitle('');
      setIngestFiles([]);
    } catch (e) {
      addToast(`Upload failed: ${(e as Error).message}`, 'err');
    } finally {
      setIngesting(false);
    }
  };

  const handleNewCaseNarrativeIngest = async () => {
    if (!newCaseTitle.trim()) { addToast('Case Title / Designation is required', 'info'); return; }
    if (!narrativeText.trim()) { addToast('Please enter intelligence narrative text', 'info'); return; }

    const targetTitle = newCaseTitle.trim();
    const existing = cases.find(c =>
      c.case_id.toLowerCase() === targetTitle.toLowerCase() ||
      (c.case_name && c.case_name.toLowerCase() === targetTitle.toLowerCase())
    );
    if (existing) {
      setAlreadyExistsModal({ caseId: existing.case_id, caseName: existing.case_name, status: existing.status });
      return;
    }

    setIngesting(true);
    try {
      const url = `/api/v1/ingest/text?case_id=${encodeURIComponent(targetTitle)}`;
      const res = await API.send<{ case_id?: string; case_already_exists?: boolean }>(url, {
        method: 'POST',
        body: narrativeText,
        headers: { 'Content-Type': 'text/plain' }
      });
      if (res.case_already_exists) {
        setAlreadyExistsModal({ caseId: res.case_id || targetTitle, caseName: targetTitle });
        await fetchCases();
        return;
      }
      addToast(`Narrative intelligence ingested for Case '${res.case_id}'!`, 'ok');
      await fetchCases();
      setIsIngestModalOpen(false);
      setNewCaseTitle('');
      setNarrativeText('');
    } catch (e) {
      addToast(`Extraction failed: ${(e as Error).message}`, 'err');
    } finally {
      setIngesting(false);
    }
  };

  // --- Handlers for Attaching File to Existing Case ---
  const handleAttachFileUpload = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!selectedCase) return;
    if (!attachFiles || attachFiles.length === 0) { addToast('Please select a file to upload', 'info'); return; }
    setAttaching(true);
    try {
      const formData = new FormData();
      for (const f of attachFiles) {
        formData.append('files', f);
        formData.append('file', f);
      }
      const res = await API.send<{ case_id?: string }>(`/api/v1/ingest?case_id=${encodeURIComponent(selectedCase)}`, {
        method: 'POST',
        body: formData,
        form: true
      });
      addToast(`File attached successfully to Case '${selectedCase}'!`, 'ok');
      await fetchCases();
      await loadCaseDetail(selectedCase);
      setIsAttachModalOpen(false);
      setAttachFiles([]);
    } catch (e) {
      addToast(`Attachment failed: ${(e as Error).message}`, 'err');
    } finally {
      setAttaching(false);
    }
  };

  const handleAttachNarrativeIngest = async () => {
    if (!selectedCase) return;
    if (!attachNarrative.trim()) { addToast('Please enter narrative text', 'info'); return; }
    setAttaching(true);
    try {
      const res = await API.send<{ case_id?: string }>(`/api/v1/ingest/text?case_id=${encodeURIComponent(selectedCase)}`, {
        method: 'POST',
        body: attachNarrative,
        headers: { 'Content-Type': 'text/plain' }
      });
      addToast(`Narrative intelligence attached to Case '${selectedCase}'!`, 'ok');
      await fetchCases();
      await loadCaseDetail(selectedCase);
      setIsAttachModalOpen(false);
      setAttachNarrative('');
    } catch (e) {
      addToast(`Extraction failed: ${(e as Error).message}`, 'err');
    } finally {
      setAttaching(false);
    }
  };

  return (
    <div>
      {/* CASE REGISTRY MAIN LIST VIEW (shown when no case is currently selected) */}
      {!selectedCase && (
        <div className="card">
          <div className="card-header flex items-center justify-between flex-wrap gap-3">
            <div className="card-title font-semibold text-lg flex items-center gap-2">
              <span>📋</span> Case Registry
            </div>
            <div className="row flex items-center gap-2.5" style={{ gap: '10px' }}>
              <button
                className="neu-btn primary flex items-center gap-2 font-semibold transition hover:opacity-90"
                onClick={() => setIsIngestModalOpen(true)}
              >
                <span>➕</span> Ingest a New Case
              </button>

              <div className="field" style={{ maxWidth: '180px' }}>
                <select
                  className="control text-sm"
                  value={statusFilter}
                  onChange={(e: React.ChangeEvent<HTMLSelectElement>) => setStatusFilter(e.target.value)}
                >
                  <option value="">All Statuses</option>
                  <option>OPEN</option>
                  <option>UNDER_INVESTIGATION</option>
                  <option>CHARGED</option>
                  <option>CLOSED</option>
                </select>
              </div>

              <button className="neu-btn ghost flex items-center gap-2 transition hover:opacity-80" onClick={fetchCases}>
                <svg viewBox="0 0 24 24" fill="none" strokeWidth="2" strokeLinecap="round" width="16" height="16"><path d="M21 12a9 9 0 1 1-2.64-6.36M21 3v6h-6"/></svg>
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
                  <tr><td colSpan={6} style={{ textAlign: 'center', padding: '30px', color: 'var(--text-faint)' }}>No cases found matching filter</td></tr>
                ) : (
                  filteredCases.map(c => (
                    <tr key={c.case_id}>
                      <td>
                        <div style={{ fontWeight: 700, color: 'var(--text)' }}>{esc(c.case_name || c.case_id)}</div>
                        <div className="mono" style={{ color: 'var(--text-faint)', fontSize: '11.5px' }}>{esc(c.case_id)}</div>
                      </td>
                      <td>{esc(c.case_type || '—')}</td>
                      <td><span className={`tag ${(c.priority || 'med').toLowerCase()}`}>{esc(c.priority || 'MEDIUM')}</span></td>
                      <td className="mono"><b>{c.total_entities}</b></td>
                      <td><span className={`tag ${(c.status || 'open').toLowerCase().includes('close') ? 'closed' : 'open'}`}>{esc(c.status || 'OPEN')}</span></td>
                      <td>
                        <div className="flex items-center gap-1.5" style={{ display: 'flex', gap: '6px' }}>
                          <button className="neu-btn ghost transition hover:opacity-80" style={{ padding: '4px 8px', fontSize: '11.5px' }} onClick={() => loadCaseDetail(c.case_id)}>Inspect</button>
                          <button className="neu-btn ghost transition hover:opacity-80" style={{ padding: '4px 8px', fontSize: '11.5px', color: 'var(--accent)' }} onClick={() => openAiDossier(c.case_id, c.case_name || c.case_id)}>✨ AI Dossier</button>
                          <button className="neu-btn ghost danger transition hover:opacity-80" style={{ padding: '4px 8px', fontSize: '11.5px' }} onClick={() => promptDeleteCase(c.case_id, c.case_name || c.case_id)}>Delete</button>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* DEDICATED FULL-PAGE CASE INSPECTION VIEW (shown when a case is selected) */}
      {selectedCase && (
        <div className="card inspect-container">
          {/* Dedicated Inspect Header with Top Back Button */}
          <div className="card-header flex items-center justify-between flex-wrap gap-4" style={{ borderBottom: '1px solid var(--border)', paddingBottom: '16px', marginBottom: '20px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
              <button
                className="neu-btn ghost flex items-center gap-2 font-semibold transition hover:opacity-90"
                style={{ padding: '8px 14px', fontSize: '13.5px', border: '1px solid var(--border)', background: 'var(--surface)' }}
                onClick={() => setSelectedCase(null)}
              >
                <span>←</span> Back to Case Registry
              </button>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                <div className="flex items-center gap-2.5 flex-wrap" style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
                  <div className="card-title font-semibold" style={{ fontSize: '20px', margin: 0 }}>
                    {esc(caseDetail?.case_name || selectedCase)}
                  </div>
                  <span className="mono tag plain" style={{ fontSize: '11px' }}>ID: {esc(selectedCase)}</span>
                  {caseDetail?.fir_number && (
                    <span className="tag" style={{ background: 'rgba(99, 102, 241, 0.14)', color: 'var(--accent-secondary)', border: '1px solid rgba(99, 102, 241, 0.3)' }}>
                      📜 FIR No: {esc(caseDetail.fir_number)}
                    </span>
                  )}
                  {caseDetail?.date && (
                    <span className="tag plain" style={{ fontSize: '11px' }}>
                      📅 {esc(caseDetail.date)}
                    </span>
                  )}
                  {caseDetail?.category_of_crime && (
                    <span className="tag" style={{ background: 'rgba(2, 132, 199, 0.14)', color: 'var(--cyan)', border: '1px solid rgba(2, 132, 199, 0.3)' }}>
                      ⚖️ {esc(caseDetail.category_of_crime)}
                    </span>
                  )}
                  {caseDetail?.priority && (
                    <span className={`tag ${(caseDetail.priority || 'med').toLowerCase()}`}>
                      {esc(caseDetail.priority)}
                    </span>
                  )}
                  {caseDetail?.status && (
                    <span className={`tag ${(caseDetail.status || 'open').toLowerCase().includes('close') ? 'closed' : 'open'}`}>
                      {esc(caseDetail.status)}
                    </span>
                  )}
                </div>
              </div>
            </div>

            <div className="flex items-center gap-2" style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
              <button
                className="neu-btn primary flex items-center gap-1.5 transition"
                onClick={() => setIsAttachModalOpen(true)}
              >
                <span>📤</span> Upload File to Case
              </button>
              <button className="neu-btn ghost transition" style={{ color: 'var(--accent)', border: '1px solid rgba(99, 102, 241, 0.3)' }} onClick={() => openAiDossier(caseDetail?.case_id || selectedCase, caseDetail?.case_name || selectedCase)}>
                ✨ AI Dossier
              </button>
              <button className="neu-btn ghost transition" onClick={() => changeView('graph')}>
                View in Graph Explorer →
              </button>
            </div>
          </div>

          {loadingDetail ? (
            <div style={{ padding: '30px 0' }}>
              <div className="skeleton sk-row"></div>
              <div className="skeleton sk-row"></div>
            </div>
          ) : !caseDetail ? (
            <div className="empty">Could not load details for case {selectedCase}</div>
          ) : (
            <div>
              {/* Cross-Case Overlap Banner */}
              {caseDetail.case_overlap?.has_overlap ? (
                <div className="overlap-banner alert-overlap-glow flex items-start gap-3" style={{ marginBottom: '20px' }}>
                  <span style={{ fontSize: '22px' }}>⚠️</span>
                  <div style={{ flex: 1 }}>
                    <div className="font-bold mb-1" style={{ fontWeight: 700, fontSize: '14px', color: 'var(--amber)', marginBottom: '4px' }}>
                      Cross-Case Linkage Detected ({caseDetail.case_overlap.overlap_count} Overlapping Case{(caseDetail.case_overlap.overlap_count || 0) > 1 ? 's' : ''})
                    </div>
                    <div style={{ fontSize: '12.5px', color: 'var(--text-dim)', marginBottom: '8px' }}>
                      This investigation shares common suspects, communication nodes, or financial accounts with other registered dockets:
                    </div>
                    <div className="flex gap-2 flex-wrap" style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                      {caseDetail.case_overlap.overlapping_cases.map((oc, oIdx) => (
                        <div key={oIdx} className="flex items-center gap-2" style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: '8px', padding: '6px 12px', fontSize: '12px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                          <span style={{ fontWeight: 700, color: 'var(--text)' }}>🔗 {esc(oc.case_name || oc.case_id)}</span>
                          <span className="mono tag plain" style={{ fontSize: '10px' }}>{esc(oc.case_id)}</span>
                          <span className="tag high" style={{ padding: '1px 6px', fontSize: '10px' }}>{oc.shared_count} shared</span>
                          {(oc.sample_entities?.length ?? 0) > 0 && (
                            <span style={{ color: 'var(--text-faint)', fontSize: '11px' }}>({oc.sample_entities!.slice(0, 2).join(', ')})</span>
                          )}
                          <button className="neu-btn ghost transition" style={{ padding: '2px 6px', fontSize: '10px', height: 'auto' }} onClick={() => loadCaseDetail(oc.case_id)}>Inspect →</button>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              ) : (
                <div className="overlap-banner clean flex items-center gap-3" style={{ marginBottom: '20px' }}>
                  <span style={{ fontSize: '20px' }}>🛡️</span>
                  <div>
                    <div className="font-bold" style={{ fontWeight: 700, fontSize: '13.5px', color: 'var(--green)' }}>Isolated Forensic Network</div>
                    <div style={{ fontSize: '12px', color: 'var(--text-faint)' }}>No multi-case entity contagion or shared suspect overlap detected with other dockets.</div>
                  </div>
                </div>
              )}

              {/* 4-Column Forensic Intelligence Grid */}
              <div className={`inspect-grid grid gap-4`} style={{ marginBottom: '20px' }}>
                {/* 1. Primary Suspects */}
                <div className="inspect-subcard">
                  <div className="inspect-subcard-title flex items-center gap-2 font-medium">
                    <span>🎯</span> Primary Suspects & Targets
                  </div>
                  <div className="inspect-subcard-content">
                    {(caseDetail.primary_suspects || []).length > 0 ? (
                      caseDetail.primary_suspects!.slice(0, 4).map((s, idx) => (
                        <div key={idx} className="actor-pill suspect flex items-center justify-between">
                          <span style={{ fontWeight: 700, color: 'var(--text)' }}>{esc(s.name)}</span>
                          <span className="tag crit" style={{ fontSize: '10px', padding: '1px 6px' }}>
                            {esc(Array.isArray(s.roles) ? s.roles.join(', ') : (s.roles || 'Suspect'))}
                          </span>
                        </div>
                      ))
                    ) : (
                      <div style={{ fontSize: '12.5px', color: 'var(--text-faint)', fontStyle: 'italic' }}>No primary suspects registered yet in graph.</div>
                    )}
                  </div>
                </div>

                {/* 2. Victims */}
                <div className="inspect-subcard">
                  <div className="inspect-subcard-title flex items-center gap-2 font-medium">
                    <span>👤</span> Victims & Complainants
                  </div>
                  <div className="inspect-subcard-content">
                    {(caseDetail.victims || []).length > 0 ? (
                      caseDetail.victims!.slice(0, 4).map((v, idx) => (
                        <div key={idx} className="actor-pill victim flex items-center justify-between">
                          <span style={{ fontWeight: 700, color: 'var(--text)' }}>{esc(v.name)}</span>
                          <span className="tag open" style={{ fontSize: '10px', padding: '1px 6px' }}>
                            {esc(Array.isArray(v.roles) ? v.roles.join(', ') : (v.roles || 'Victim'))}
                          </span>
                        </div>
                      ))
                    ) : (
                      <div style={{ fontSize: '12.5px', color: 'var(--text-faint)', fontStyle: 'italic' }}>No victims or complainants explicitly tagged.</div>
                    )}
                  </div>
                </div>

                {/* 3. Evidences Collected So Far */}
                <div className="inspect-subcard">
                  <div className="inspect-subcard-title flex items-center gap-2 font-medium">
                    <span>🗂️</span> Evidences Collected So Far
                  </div>
                  <div className="inspect-subcard-content">
                    <div className="flex flex-wrap gap-1.5" style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                      {(caseDetail.evidences_collected || []).map((ev, eIdx) => (
                        <div key={eIdx} className="evidence-chip flex items-center gap-1">
                          <span>{ev.icon}</span>
                          <span>{esc(ev.name)}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                {/* 4. Investigation & Legal Details */}
                <div className="inspect-subcard">
                  <div className="inspect-subcard-title flex items-center gap-2 font-medium">
                    <span>🏛️</span> Legal & Jurisdictional Record
                  </div>
                  <div className="inspect-subcard-content">
                    <div className="flex flex-col gap-1.5 text-xs" style={{ display: 'flex', flexDirection: 'column', gap: '6px', fontSize: '12.5px' }}>
                      <div className="flex justify-between" style={{ display: 'flex', justifyContent: 'space-between' }}>
                        <span style={{ color: 'var(--text-faint)' }}>FIR Number:</span>
                        <span className="mono font-bold" style={{ fontWeight: 700 }}>{esc(caseDetail.fir_number || 'N/A')}</span>
                      </div>
                      <div className="flex justify-between" style={{ display: 'flex', justifyContent: 'space-between' }}>
                        <span style={{ color: 'var(--text-faint)' }}>Crime Category:</span>
                        <span className="font-semibold" style={{ fontWeight: 600 }}>{esc(caseDetail.category_of_crime || caseDetail.case_type || 'N/A')}</span>
                      </div>
                      <div className="flex justify-between" style={{ display: 'flex', justifyContent: 'space-between' }}>
                        <span style={{ color: 'var(--text-faint)' }}>Incident / Reg Date:</span>
                        <span>{esc(caseDetail.date || caseDetail.created_at || '—')}</span>
                      </div>
                      <div className="flex justify-between" style={{ display: 'flex', justifyContent: 'space-between' }}>
                        <span style={{ color: 'var(--text-faint)' }}>Lead Officer:</span>
                        <span>{esc(caseDetail.lead_investigator || 'Special Investigation Unit')}</span>
                      </div>
                      <div className="flex justify-between" style={{ display: 'flex', justifyContent: 'space-between' }}>
                        <span style={{ color: 'var(--text-faint)' }}>Total Graph Nodes:</span>
                        <span className="mono font-bold" style={{ fontWeight: 700, color: 'var(--accent)' }}>{caseDetail.total_entities || 0} entities</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Case Narrative Summary */}
              <div style={{ marginBottom: '20px', background: 'var(--bg1)', border: '1px solid var(--border)', borderRadius: '12px', padding: '16px' }}>
                <div style={{ fontSize: '12px', textTransform: 'uppercase', letterSpacing: '0.6px', fontWeight: 700, color: 'var(--text-faint)', marginBottom: '6px' }}>
                  Investigation Synopsis & Operational Narrative
                </div>
                <div style={{ fontSize: '13.5px', color: 'var(--text)', lineHeight: 1.6 }}>
                  {esc(caseDetail.summary || 'No narrative summary provided for this case.')}
                </div>
              </div>

              {/* Subnetwork Topology Mini-Graph */}
              <div style={{ background: 'var(--bg1)', border: '1px solid var(--border)', borderRadius: '12px', padding: '16px' }}>
                <div className="flex justify-between items-center mb-3" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                  <div className="font-bold text-sm flex items-center gap-2" style={{ fontWeight: 700, fontSize: '14px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span>🕸️</span> Subnetwork Visual Topology
                    <span className="mono tag plain" style={{ fontSize: '11px' }}>{caseDetail.total_entities || 0} Nodes</span>
                  </div>
                  <div className="text-xs" style={{ fontSize: '12px', color: 'var(--text-faint)' }}>
                    Interactive sub-topology view · Click node to inspect details
                  </div>
                </div>
                <div style={{ width: '100%', height: '360px', borderRadius: '10px', border: '1px solid var(--border)', background: 'var(--graph-bg)', overflow: 'hidden' }} ref={miniGraphRef}></div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* MODAL 1: INGEST A NEW CASE MODAL */}
      {isIngestModalOpen && (
        <div className="modal-overlay open" onClick={(e) => { if (e.target === e.currentTarget) setIsIngestModalOpen(false); }}>
          <div className="modal" style={{ maxWidth: '680px', width: '90%' }}>
            <div className="modal-header flex items-center justify-between mb-4 pb-3" style={{ borderBottom: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', paddingBottom: '12px' }}>
              <div className="modal-title font-bold text-lg flex items-center gap-2" style={{ fontSize: '18px', fontWeight: 700 }}>
                <span>➕</span> Ingest a New Case
              </div>
              <button className="neu-btn ghost" style={{ padding: '2px 8px', fontSize: '14px' }} onClick={() => setIsIngestModalOpen(false)}>✕</button>
            </div>

            <div className="modal-body flex flex-col gap-4" style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              {/* Required Case Title Input */}
              <div className="field">
                <label className="field-label font-bold text-xs uppercase" style={{ display: 'block', marginBottom: '6px', fontSize: '11.5px', fontWeight: 700, color: 'var(--text-dim)' }}>
                  Case Title / Designation <span style={{ color: 'var(--accent)', fontSize: '14px' }}>*</span> (Required)
                </label>
                <input
                  type="text"
                  required
                  className="control w-full text-sm"
                  placeholder="e.g. Operation Cyber Shield / FIR-2026-902"
                  value={newCaseTitle}
                  onChange={(e) => setNewCaseTitle(e.target.value)}
                  style={{ width: '100%', padding: '8px 12px', borderColor: !newCaseTitle.trim() ? 'var(--border)' : undefined }}
                />
                <span style={{ fontSize: '11px', color: !newCaseTitle.trim() ? 'var(--accent)' : 'var(--text-faint)', marginTop: '4px', display: 'block' }}>
                  {!newCaseTitle.trim() ? '⚠️ Please specify a mandatory Case Title or Designation for this new case.' : 'Case designation registered.'}
                </span>
              </div>

              {/* Source Mode Tabs */}
              <div className="flex gap-2 border-b pb-2" style={{ display: 'flex', gap: '8px', borderBottom: '1px solid var(--border)', paddingBottom: '8px' }}>
                <button
                  className={`neu-btn transition-colors ${ingestTab === 'file' ? 'primary' : 'ghost'}`}
                  style={{ padding: '6px 12px', fontSize: '12.5px' }}
                  onClick={() => setIngestTab('file')}
                >
                  📁 Upload Document (.pdf, .json, .csv, .txt)
                </button>
                <button
                  className={`neu-btn transition-colors ${ingestTab === 'json' ? 'primary' : 'ghost'}`}
                  style={{ padding: '6px 12px', fontSize: '12.5px' }}
                  onClick={() => setIngestTab('json')}
                >
                  Structured JSON Payload
                </button>
                <button
                  className={`neu-btn transition-colors ${ingestTab === 'narrative' ? 'primary' : 'ghost'}`}
                  style={{ padding: '6px 12px', fontSize: '12.5px' }}
                  onClick={() => setIngestTab('narrative')}
                >
                  Unstructured Text Narrative
                </button>
              </div>

              {/* Tab 1: File Upload */}
              {ingestTab === 'file' && (
                <form onSubmit={handleNewCaseFileUpload} className="flex flex-col gap-4">
                  <div style={{ padding: '24px 16px', border: '2px dashed var(--border)', borderRadius: '8px', textAlign: 'center', background: 'var(--bg1)' }}>
                    <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="var(--text-faint)" strokeWidth="1.5" style={{ margin: '0 auto 10px' }}><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M17 8l-5-5-5 5M12 3v12"/></svg>
                    <div style={{ fontWeight: 700, fontSize: '14px', marginBottom: '4px' }}>Select case document or data sheet</div>
                    <div style={{ fontSize: '12px', color: 'var(--text-faint)', marginBottom: '14px' }}>
                      Supports `.pdf` FIR reports, `.csv` call logs, `.json` dossiers, `.txt` narratives
                    </div>
                    <input
                      type="file"
                      accept=".json,.csv,.pdf,.txt,.log"
                      multiple
                      onChange={(e) => setIngestFiles(Array.from(e.target.files || []))}
                      style={{ display: 'inline-block' }}
                    />
                    {ingestFiles.length > 0 && (
                      <div style={{ marginTop: '10px', fontSize: '12.5px', color: 'var(--accent)', fontWeight: 600 }}>
                        Selected {ingestFiles.length} file{ingestFiles.length > 1 ? 's' : ''}: {ingestFiles.map(f => f.name).join(', ')}
                      </div>
                    )}
                  </div>
                  <div className="flex justify-end gap-2" style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '10px' }}>
                    <button type="button" className="neu-btn ghost" onClick={() => setIsIngestModalOpen(false)}>Cancel</button>
                    <button type="submit" className="neu-btn primary" disabled={ingesting || ingestFiles.length === 0 || !newCaseTitle.trim()}>
                      {ingesting ? 'Uploading & Extracting…' : 'Ingest New Case'}
                    </button>
                  </div>
                </form>
              )}

              {/* Tab 2: JSON Payload */}
              {ingestTab === 'json' && (
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                    <label style={{ fontSize: '11.5px', fontWeight: 700, color: 'var(--text-dim)', textTransform: 'uppercase' }}>JSON Payload</label>
                    <button className="neu-btn ghost" style={{ padding: '2px 6px', fontSize: '11px' }} onClick={() => setJsonText(JSON.stringify(sampleJson, null, 2))}>
                      Load Sample JSON
                    </button>
                  </div>
                  <textarea
                    className="control mono"
                    rows={10}
                    style={{ width: '100%', fontSize: '12px', lineHeight: 1.5 }}
                    value={jsonText}
                    onChange={(e) => setJsonText(e.target.value)}
                    placeholder="Paste Case JSON structure here..."
                  />
                  <div className="flex justify-end gap-2" style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '14px' }}>
                    <button type="button" className="neu-btn ghost" onClick={() => setIsIngestModalOpen(false)}>Cancel</button>
                    <button className="neu-btn primary" disabled={ingesting || !newCaseTitle.trim()} onClick={handleNewCaseJsonIngest}>
                      {ingesting ? 'Ingesting into Graph…' : 'Commit to Neo4j Graph'}
                    </button>
                  </div>
                </div>
              )}

              {/* Tab 3: Unstructured Text Narrative */}
              {ingestTab === 'narrative' && (
                <div>
                  <label style={{ display: 'block', fontSize: '11.5px', fontWeight: 700, color: 'var(--text-dim)', textTransform: 'uppercase', marginBottom: '8px' }}>
                    Informant / FIR Narrative Text
                  </label>
                  <textarea
                    className="control"
                    rows={8}
                    style={{ width: '100%', fontSize: '13px', lineHeight: 1.5 }}
                    value={narrativeText}
                    onChange={(e) => setNarrativeText(e.target.value)}
                    placeholder="Paste complaint or report text here..."
                  />
                  <div className="flex justify-end gap-2" style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '14px' }}>
                    <button type="button" className="neu-btn ghost" onClick={() => setIsIngestModalOpen(false)}>Cancel</button>
                    <button className="neu-btn primary" disabled={ingesting || !newCaseTitle.trim()} onClick={handleNewCaseNarrativeIngest}>
                      {ingesting ? 'Extracting Entities via AI…' : 'Ingest via AI Engine'}
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* MODAL 2: UPLOAD FILE DIRECTLY TO EXISTING CASE MODAL */}
      {isAttachModalOpen && selectedCase && (
        <div className="modal-overlay open" onClick={(e) => { if (e.target === e.currentTarget) setIsAttachModalOpen(false); }}>
          <div className="modal" style={{ maxWidth: '620px', width: '90%' }}>
            <div className="modal-header flex items-center justify-between mb-4 pb-3" style={{ borderBottom: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', paddingBottom: '12px' }}>
              <div>
                <div className="modal-title font-bold text-lg flex items-center gap-2" style={{ fontSize: '18px', fontWeight: 700 }}>
                  <span>📤</span> Attach Document to Case
                </div>
                <div style={{ fontSize: '12px', color: 'var(--text-faint)', marginTop: '2px' }}>
                  Target Case ID: <span className="mono font-bold" style={{ color: 'var(--accent)' }}>{selectedCase}</span>
                </div>
              </div>
              <button className="neu-btn ghost" style={{ padding: '2px 8px', fontSize: '14px' }} onClick={() => setIsAttachModalOpen(false)}>✕</button>
            </div>

            <div className="modal-body flex flex-col gap-4" style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div className="flex gap-2 border-b pb-2" style={{ display: 'flex', gap: '8px', borderBottom: '1px solid var(--border)', paddingBottom: '8px' }}>
                <button
                  className={`neu-btn transition-colors ${attachTab === 'file' ? 'primary' : 'ghost'}`}
                  style={{ padding: '6px 12px', fontSize: '12.5px' }}
                  onClick={() => setAttachTab('file')}
                >
                  📁 File Upload (.pdf, .json, .csv, .txt)
                </button>
                <button
                  className={`neu-btn transition-colors ${attachTab === 'narrative' ? 'primary' : 'ghost'}`}
                  style={{ padding: '6px 12px', fontSize: '12.5px' }}
                  onClick={() => setAttachTab('narrative')}
                >
                  Text Narrative / Addendum
                </button>
              </div>

              {attachTab === 'file' && (
                <form onSubmit={handleAttachFileUpload} className="flex flex-col gap-4">
                  <div style={{ padding: '24px 16px', border: '2px dashed var(--border)', borderRadius: '8px', textAlign: 'center', background: 'var(--bg1)' }}>
                    <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="var(--text-faint)" strokeWidth="1.5" style={{ margin: '0 auto 10px' }}><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M17 8l-5-5-5 5M12 3v12"/></svg>
                    <div style={{ fontWeight: 700, fontSize: '14px', marginBottom: '4px' }}>Select document or data file</div>
                    <div style={{ fontSize: '12px', color: 'var(--text-faint)', marginBottom: '14px' }}>
                      Will extract entities directly into case <span className="mono">{selectedCase}</span> without creating a new case
                    </div>
                    <input
                      type="file"
                      accept=".json,.csv,.pdf,.txt,.log"
                      multiple
                      onChange={(e) => setAttachFiles(Array.from(e.target.files || []))}
                      style={{ display: 'inline-block' }}
                    />
                    {attachFiles.length > 0 && (
                      <div style={{ marginTop: '10px', fontSize: '12.5px', color: 'var(--accent)', fontWeight: 600 }}>
                        Selected {attachFiles.length} file{attachFiles.length > 1 ? 's' : ''}: {attachFiles.map(f => f.name).join(', ')}
                      </div>
                    )}
                  </div>
                  <div className="flex justify-end gap-2" style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '10px' }}>
                    <button type="button" className="neu-btn ghost" onClick={() => setIsAttachModalOpen(false)}>Cancel</button>
                    <button type="submit" className="neu-btn primary" disabled={attaching || attachFiles.length === 0}>
                      {attaching ? 'Uploading & Extracting…' : 'Attach File to Case'}
                    </button>
                  </div>
                </form>
              )}

              {attachTab === 'narrative' && (
                <div>
                  <label style={{ display: 'block', fontSize: '11.5px', fontWeight: 700, color: 'var(--text-dim)', textTransform: 'uppercase', marginBottom: '8px' }}>
                    Addendum Report / Narrative Text
                  </label>
                  <textarea
                    className="control"
                    rows={8}
                    style={{ width: '100%', fontSize: '13px', lineHeight: 1.5 }}
                    value={attachNarrative}
                    onChange={(e) => setAttachNarrative(e.target.value)}
                    placeholder="Paste additional narrative intelligence to append to this case..."
                  />
                  <div className="flex justify-end gap-2" style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '14px' }}>
                    <button type="button" className="neu-btn ghost" onClick={() => setIsAttachModalOpen(false)}>Cancel</button>
                    <button className="neu-btn primary" disabled={attaching} onClick={handleAttachNarrativeIngest}>
                      {attaching ? 'Extracting & Merging…' : 'Attach Narrative to Case'}
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* MODAL 3: CASE ALREADY EXISTS ALERT POPUP */}
      {alreadyExistsModal && (
        <CaseAlreadyExistsModal
          caseId={alreadyExistsModal.caseId}
          caseName={alreadyExistsModal.caseName}
          status={alreadyExistsModal.status}
          onClose={() => setAlreadyExistsModal(null)}
          onViewCase={(cid) => {
            loadCaseDetail(cid);
            setIsIngestModalOpen(false);
          }}
        />
      )}
    </div>
  );
}
