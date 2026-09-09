import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { API, esc, Case, Insight } from '../services/api';

declare module '../services/api' {
  interface Insight {
    insight_type?: string;
    title?: string;
    derived_interpretation?: string;
    observed_facts?: string[];
    case_ids?: string[];
    alternative_explanations?: string[];
    disclaimer?: string;
  }
}

export interface PatternInsightsModuleProps {
  cases: Case[];
  insights: Insight[];
  setInsights: (insights: Insight[]) => void;
  openAiDossier: (caseId: string, caseName: string) => void;
  addToast: (msg: string, type?: string) => void;
}

export function PatternInsightsModule({
  cases,
  insights,
  setInsights,
  openAiDossier,
  addToast
}: PatternInsightsModuleProps) {
  const [selectedCase, setSelectedCase] = useState<string>('');
  const [severityFilter, setSeverityFilter] = useState<string>('');
  const [selectedInsight, setSelectedInsight] = useState<Insight | null>(null);
  const [loading, setLoading] = useState<boolean>(false);

  const fetchInsights = useCallback(async () => {
    setLoading(true);
    try {
      let list: Insight[] = [];
      if (selectedCase === '__DELTA__') {
        list = await API.get<Insight[]>('/api/insights/delta');
      } else if (selectedCase) {
        list = await API.get<Insight[]>(`/api/cases/${encodeURIComponent(selectedCase)}/insights`);
      } else {
        const allResults = await Promise.all(
          cases.map(c => API.get<Insight[]>(`/api/cases/${encodeURIComponent(c.case_id)}/insights`).catch(() => []))
        );
        list = allResults.flat();
        const seen = new Set<string>();
        list = list.filter(i => {
          if (!i.insight_id || seen.has(i.insight_id)) return false;
          seen.add(i.insight_id);
          return true;
        });
      }
      setInsights(list);
    } catch (e) {
      addToast((e as Error).message, 'err');
    } finally {
      setLoading(false);
    }
  }, [selectedCase, cases, setInsights, addToast]);

  useEffect(() => {
    fetchInsights();
  }, [fetchInsights]);

  const filteredInsights = useMemo(() => {
    if (!severityFilter) return insights;
    return (insights || []).filter(i => (i.severity || '').toUpperCase() === severityFilter);
  }, [insights, severityFilter]);

  return (
    <div>
      <div className="card">
        <div className="card-header flex items-center justify-between">
          <div className="card-title font-semibold text-base">Automated Forensic Detectors</div>
          <div className="row flex flex-wrap items-center gap-2.5" style={{gap:'10px', flexWrap:'wrap'}}>
            <div className="field" style={{minWidth:'200px'}}>
              <select className="control" value={selectedCase} onChange={(e: React.ChangeEvent<HTMLSelectElement>) => setSelectedCase(e.target.value)}>
                <option value="">All Ingested Cases</option>
                <option value="__DELTA__">Cross-Case Delta Insights Only</option>
                {cases.map(c => <option key={c.case_id} value={c.case_id}>Case: {esc(c.case_name || c.case_id)}</option>)}
              </select>
            </div>
            <select className="control" value={severityFilter} onChange={(e: React.ChangeEvent<HTMLSelectElement>) => setSeverityFilter(e.target.value)} style={{maxWidth:'160px'}}>
              <option value="">All Severities</option>
              <option value="CRITICAL">CRITICAL</option>
              <option value="HIGH">HIGH</option>
              <option value="MEDIUM">MEDIUM</option>
              <option value="LOW">LOW</option>
            </select>
            <button className="neu-btn primary inline-flex items-center gap-1.5 transition-colors" onClick={() => {
              if (selectedCase && selectedCase !== '__DELTA__') {
                const cObj = cases.find(c => c.case_id === selectedCase);
                openAiDossier(selectedCase, cObj?.case_name || selectedCase);
              } else if (cases.length) {
                openAiDossier(cases[0].case_id, cases[0].case_name || cases[0].case_id);
              } else {
                addToast('Please select a case to generate AI Dossier', 'info');
              }
            }} style={{display:'inline-flex', alignItems:'center', gap:'6px'}}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="m12 3-1.9 5.8a2 2 0 0 1-1.3 1.3L3 12l5.8 1.9a2 2 0 0 1 1.3 1.3L12 21l1.9-5.8a2 2 0 0 1 1.3-1.3L21 12l-5.8-1.9a2 2 0 0 1-1.3-1.3Z"/></svg>
              ✨ AI Dossier
            </button>
          </div>
        </div>
      </div>

      {loading ? (
        <div><div className="skeleton sk-row"></div><div className="skeleton sk-row"></div></div>
      ) : !filteredInsights || !filteredInsights.length ? (
        <div className="empty">
          <svg viewBox="0 0 24 24" fill="none" strokeWidth="2"><path d="M12 3l1.9 5.6L19 10l-5.1 1.9L12 17.5l-1.9-5.6L5 10l5.1-1.4L12 3Z"/></svg>
          No pattern insights match the selected filter. Ingest additional cases or communications to trigger detection.
        </div>
      ) : (
        <div className="cards-grid" style={{gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))'}}>
          {filteredInsights.map(i => {
            const sev = (i.severity || 'MEDIUM').toUpperCase();
            const sevClass = sev === 'CRITICAL' ? 'crit' : sev === 'HIGH' ? 'high' : sev === 'MEDIUM' ? 'med' : 'low';
            return (
              <div key={i.insight_id} className="card transition-all duration-200 flex flex-col" style={{marginBottom:0, display:'flex', flexDirection:'column'}}>
                <div className="flex items-center justify-between gap-2 mb-3" style={{display:'flex', alignItems:'center', justifyContent:'space-between', gap:'8px', marginBottom:'12px'}}>
                  <span className={`tag ${sevClass}`}>{sev}</span>
                  <span className="mono text-xs" style={{fontSize:'11px', color:'var(--text-faint)'}}>{esc(i.insight_type)}</span>
                </div>
                <div className="font-bold text-sm text-foreground mb-2" style={{fontWeight:700, fontSize:'15px', marginBottom:'8px', color:'var(--text)'}}>{esc(i.title)}</div>
                <div style={{fontSize:'13px', color:'var(--text-dim)', marginBottom:'14px', flex:1, lineHeight:1.5}}>{esc(i.derived_interpretation)}</div>
                {(i.observed_facts || []).slice(0, 2).map((f, idx) => (
                  <div key={idx} className="flex gap-1.5 mb-1 text-xs" style={{fontSize:'12px', color:'var(--text-faint)', display:'flex', gap:'6px', marginBottom:'4px'}}>
                    <span style={{color:'var(--accent)'}}>●</span> {esc(f)}
                  </div>
                ))}
                <div className="flex gap-1.5 flex-wrap mt-3.5" style={{marginTop:'14px', display:'flex', gap:'6px', flexWrap:'wrap'}}>
                  {(i.case_ids || []).map(c => <span key={c} className="tag plain mono">{esc(c)}</span>)}
                </div>
                <button className="neu-btn ghost w-full mt-3.5 transition-colors" style={{marginTop:'14px', width:'100%'}} onClick={() => setSelectedInsight(i)}>Examine Evidence</button>
              </div>
            );
          })}
        </div>
      )}

      {selectedInsight && (
        <div className="modal-overlay open" onClick={() => setSelectedInsight(null)}>
          <div className="modal" onClick={(e: React.MouseEvent<HTMLDivElement>) => e.stopPropagation()}>
            <button className="close neu-btn ghost" onClick={() => setSelectedInsight(null)} style={{float:'right'}}>✕</button>
            <div className="flex items-center gap-2.5 mb-2.5" style={{display:'flex', alignItems:'center', gap:'10px', marginBottom:'10px'}}>
              <span className={`tag ${(selectedInsight.severity||'med').toLowerCase()}`}>{esc(selectedInsight.severity)}</span>
              <span className="tag plain mono">{esc(selectedInsight.insight_type)} · {esc(selectedInsight.insight_id)}</span>
            </div>
            <h3 className="font-bold text-lg">{esc(selectedInsight.title)}</h3>
            <div style={{fontSize:'14.5px', color:'var(--text)', marginBottom:'18px', lineHeight:1.6}}>{esc(selectedInsight.derived_interpretation)}</div>
            <div style={{fontWeight:700, fontSize:'13.5px', marginBottom:'8px'}}>Observed Graph Facts</div>
            {(selectedInsight.observed_facts || []).map((f, idx) => (
              <div key={idx} className="flex gap-2 mb-1.5 text-sm" style={{fontSize:'13px', color:'var(--text-dim)', marginBottom:'6px', display:'flex', gap:'8px'}}>
                <span style={{color:'var(--accent)'}}>➔</span> {esc(f)}
              </div>
            ))}
            {(selectedInsight.alternative_explanations || []).length > 0 && (
              <React.Fragment>
                <div style={{fontWeight:700, fontSize:'13.5px', margin:'18px 0 8px'}}>Alternative Explanations</div>
                {selectedInsight.alternative_explanations?.map((a, idx) => <div key={idx} style={{fontSize:'13px', color:'var(--text-faint)', marginBottom:'4px'}}>· {esc(a)}</div>)}
              </React.Fragment>
            )}
            <div className="p-3 rounded-lg border text-xs" style={{marginTop:'20px', padding:'12px', borderRadius:'10px', background:'var(--bg1)', border:'1px solid var(--border)', fontSize:'12px', color:'var(--text-faint)'}}>
              {esc(selectedInsight.disclaimer || 'Intelligence alert generated automatically from graph topology.')}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
