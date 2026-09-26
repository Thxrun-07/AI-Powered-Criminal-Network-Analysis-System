import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { API, esc, Case, Insight } from '../services/api';
import { renderInlineMarkdown } from './FormattedAiMessage';

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

// Canonical grouping of 10 insight types into 5 investigative domains (without icons)
export interface InsightCategory {
  id: string;
  name: string;
  description: string;
  types: string[];
}

export const INSIGHT_CATEGORIES: InsightCategory[] = [
  {
    id: 'syndicate',
    name: 'Syndicate & Cross-Case Overlaps',
    description: 'Shared entities, bridge operatives, and cross-case telecommunication links connecting separate investigations',
    types: ['SHARED_ENTITY', 'CROSS_CASE_LINK', 'BRIDGE_NODE']
  },
  {
    id: 'financial',
    name: 'Financial Laundering & Flow Chains',
    description: 'Multi-hop transfer chains, collection funnels (high fan-in), and fund dispersal hubs (high fan-out)',
    types: ['TRANSFER_CHAIN', 'HIGH_FAN_IN', 'HIGH_FAN_OUT']
  },
  {
    id: 'infrastructure',
    name: 'Cyber & Hardware Infrastructure',
    description: 'Burner handset IMEI reuse across SIM cards and shared network IP / VPN exit nodes',
    types: ['INFRASTRUCTURE_REUSE']
  },
  {
    id: 'behavioral',
    name: 'Movement & Cross-Domain Coordination',
    description: 'Physical co-location at critical landmarks and telecommunication directly preceding bank transfers',
    types: ['POSSIBLE_CO_LOCATION', 'CROSS_DOMAIN_PATH']
  },
  {
    id: 'records',
    name: 'Historical Police Records & Prior FIRs',
    description: 'Matches against historical police archives, previous FIR dockets, and prior offenses',
    types: ['PRIOR_CASE_LINK']
  }
];

export const INSIGHT_TYPE_LABELS: Record<string, string> = {
  SHARED_ENTITY: 'Shared Entity',
  CROSS_CASE_LINK: 'Cross-Case Call',
  BRIDGE_NODE: 'Bridge Actor',
  TRANSFER_CHAIN: 'Transfer Chain',
  HIGH_FAN_IN: 'Collection Funnel',
  HIGH_FAN_OUT: 'Fund Dispersal',
  INFRASTRUCTURE_REUSE: 'Hardware / IP Reuse',
  POSSIBLE_CO_LOCATION: 'Co-Location',
  CROSS_DOMAIN_PATH: 'Telecom-to-Bank Link',
  PRIOR_CASE_LINK: 'Prior Record Match'
};

export function PatternInsightsModule({
  cases,
  insights,
  setInsights,
  addToast
}: PatternInsightsModuleProps) {
  const [activeCategory, setActiveCategory] = useState<string>('all');
  const [selectedInsight, setSelectedInsight] = useState<Insight | null>(null);
  const [loading, setLoading] = useState<boolean>(false);

  const fetchInsights = useCallback(async () => {
    setLoading(true);
    try {
      const allResults = await Promise.all(
        cases.map(c => API.get<Insight[]>(`/api/cases/${encodeURIComponent(c.case_id)}/insights`).catch(() => []))
      );
      let list = allResults.flat();
      const seen = new Set<string>();
      list = list.filter(i => {
        if (!i.insight_id || seen.has(i.insight_id)) return false;
        seen.add(i.insight_id);
        return true;
      });
      setInsights(list);
    } catch (e) {
      addToast((e as Error).message, 'err');
    } finally {
      setLoading(false);
    }
  }, [cases, setInsights, addToast]);

  useEffect(() => {
    fetchInsights();
  }, [fetchInsights]);

  // KPIs
  const kpis = useMemo(() => {
    const total = (insights || []).length;
    const critical = (insights || []).filter(i => (i.severity || '').toUpperCase() === 'CRITICAL').length;
    const high = (insights || []).filter(i => (i.severity || '').toUpperCase() === 'HIGH').length;
    const crossCase = (insights || []).filter(i => (i.case_ids || []).length > 1 || (i.insight_type || '').includes('CROSS')).length;
    return { total, critical, high, crossCase };
  }, [insights]);

  // Counts per category
  const categoryCounts = useMemo(() => {
    const counts: Record<string, number> = { all: (insights || []).length };
    INSIGHT_CATEGORIES.forEach(cat => {
      counts[cat.id] = (insights || []).filter(i => cat.types.includes(i.insight_type || '')).length;
    });
    return counts;
  }, [insights]);

  // Filtered insights list based on investigative domain dropdown
  const filteredInsights = useMemo(() => {
    let list = insights || [];
    if (activeCategory !== 'all') {
      const cat = INSIGHT_CATEGORIES.find(c => c.id === activeCategory);
      if (cat) {
        list = list.filter(i => cat.types.includes(i.insight_type || ''));
      }
    }
    return list;
  }, [insights, activeCategory]);

  // Grouped by Category data
  const groupedByCategory = useMemo(() => {
    const groups: Array<{ category: InsightCategory; items: Insight[] }> = [];
    INSIGHT_CATEGORIES.forEach(cat => {
      if (activeCategory !== 'all' && activeCategory !== cat.id) return;
      const items = (insights || []).filter(i => cat.types.includes(i.insight_type || ''));
      if (items.length > 0 || activeCategory === cat.id) {
        groups.push({ category: cat, items });
      }
    });
    return groups;
  }, [insights, activeCategory]);

  // Helper renderer for a single insight card (no icons)
  const renderInsightCard = (i: Insight) => {
    const sev = (i.severity || 'MEDIUM').toUpperCase();
    const sevClass = sev === 'CRITICAL' ? 'crit' : sev === 'HIGH' ? 'high' : sev === 'MEDIUM' ? 'med' : 'low';
    const typeLabel = INSIGHT_TYPE_LABELS[i.insight_type || ''] || i.insight_type || 'Insight';

    return (
      <div
        key={i.insight_id}
        className="card insight-card transition-all duration-200"
        style={{
          marginBottom: 0,
          display: 'flex',
          flexDirection: 'column',
          borderLeft: sev === 'CRITICAL' ? '4px solid #ef4444' : sev === 'HIGH' ? '4px solid #f59e0b' : '1px solid var(--border)',
          background: 'var(--surface)'
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '8px', marginBottom: '10px' }}>
          <span className={`tag ${sevClass}`} style={{ fontSize: '10px', padding: '2px 8px' }}>
            {sev}
          </span>
          <span className="tag plain mono" style={{ fontSize: '10.5px' }}>
            {typeLabel}
          </span>
        </div>

        <div style={{ fontWeight: 700, fontSize: '14px', marginBottom: '10px', color: 'var(--text)', lineHeight: 1.35 }}>
          {renderInlineMarkdown(esc(i.title))}
        </div>

        {/* Observed facts snippet */}
        {(i.observed_facts || []).slice(0, 2).map((f, idx) => (
          <div key={idx} style={{ fontSize: '11.5px', color: 'var(--text-faint)', display: 'flex', gap: '6px', marginBottom: '4px' }}>
            <span style={{ color: 'var(--text-faint)' }}>-</span>
            <div style={{ flex: 1 }}>{renderInlineMarkdown(esc(f))}</div>
          </div>
        ))}

        {/* Associated Case IDs */}
        <div style={{ marginTop: '12px', display: 'flex', gap: '5px', flexWrap: 'wrap', alignItems: 'center' }}>
          <span style={{ fontSize: '10.5px', color: 'var(--text-faint)', marginRight: '2px' }}>Cases:</span>
          {(i.case_ids || []).map(c => (
            <span
              key={c}
              className="tag open mono"
              style={{ fontSize: '10px', padding: '1px 6px' }}
            >
              {esc(c)}
            </span>
          ))}
        </div>

        <button
          type="button"
          className="neu-btn ghost w-full transition-colors"
          style={{ marginTop: '12px', width: '100%', fontSize: '11.5px', padding: '6px 12px' }}
          onClick={() => setSelectedInsight(i)}
        >
          Examine Evidence
        </button>
      </div>
    );
  };

  return (
    <div className="flex flex-col gap-4" style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      {/* Top Forensic Analytics KPIs - No Icons */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '12px' }}>
        <div className="card" style={{ marginBottom: 0, padding: '14px 18px' }}>
          <div style={{ fontSize: '10px', color: 'var(--text-faint)', textTransform: 'uppercase', letterSpacing: '0.05em', fontWeight: 700 }}>
            TOTAL DETECTIONS
          </div>
          <div style={{ fontSize: '22px', fontWeight: 800, color: 'var(--text)', marginTop: '4px' }}>
            {kpis.total}
          </div>
        </div>

        <div className="card" style={{ marginBottom: 0, padding: '14px 18px' }}>
          <div style={{ fontSize: '10px', color: 'var(--text-faint)', textTransform: 'uppercase', letterSpacing: '0.05em', fontWeight: 700 }}>
            CRITICAL THREATS
          </div>
          <div style={{ fontSize: '22px', fontWeight: 800, color: '#ef4444', marginTop: '4px' }}>
            {kpis.critical}
          </div>
        </div>

        <div className="card" style={{ marginBottom: 0, padding: '14px 18px' }}>
          <div style={{ fontSize: '10px', color: 'var(--text-faint)', textTransform: 'uppercase', letterSpacing: '0.05em', fontWeight: 700 }}>
            HIGH SEVERITY
          </div>
          <div style={{ fontSize: '22px', fontWeight: 800, color: '#f59e0b', marginTop: '4px' }}>
            {kpis.high}
          </div>
        </div>

        <div className="card" style={{ marginBottom: 0, padding: '14px 18px' }}>
          <div style={{ fontSize: '10px', color: 'var(--text-faint)', textTransform: 'uppercase', letterSpacing: '0.05em', fontWeight: 700 }}>
            CROSS-CASE OVERLAPS
          </div>
          <div style={{ fontSize: '22px', fontWeight: 800, color: 'var(--text)', marginTop: '4px' }}>
            {kpis.crossCase}
          </div>
        </div>
      </div>

      {/* Clean Domain Filter Section - Dropdown Selection */}
      <div className="card" style={{ marginBottom: 0, padding: '16px 18px' }}>
        <div className="field" style={{ maxWidth: '380px' }}>
          <label style={{ fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--text-faint)', marginBottom: '8px', display: 'block' }}>
            Filter by Investigative Domain
          </label>
          <select
            className="control"
            value={activeCategory}
            onChange={(e: React.ChangeEvent<HTMLSelectElement>) => setActiveCategory(e.target.value)}
            style={{ fontSize: '12px', padding: '7px 12px', width: '100%' }}
          >
            <option value="all">All Domains ({categoryCounts.all || 0})</option>
            {INSIGHT_CATEGORIES.map(cat => (
              <option key={cat.id} value={cat.id}>
                {cat.name} ({categoryCounts[cat.id] || 0})
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Main Content Area */}
      {loading ? (
        <div>
          <div className="skeleton sk-row"></div>
          <div className="skeleton sk-row"></div>
        </div>
      ) : !filteredInsights || !filteredInsights.length ? (
        <div className="empty card" style={{ padding: '36px 20px', textAlign: 'center' }}>
          <div style={{ fontWeight: 600, color: 'var(--text)' }}>No Pattern Insights Found</div>
          <div style={{ fontSize: '12px', color: 'var(--text-faint)', maxWidth: '420px', marginTop: '4px' }}>
            No detected graph patterns match your selected investigative domain.
          </div>
        </div>
      ) : activeCategory === 'all' ? (
        /* When 'All Domains' is selected: Organized by domain categories */
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {groupedByCategory.map(({ category, items }) => (
            <div key={category.id} className="card" style={{ marginBottom: 0, padding: 0, overflow: 'hidden' }}>
              {/* Category Group Header (No icons) */}
              <div
                style={{
                  padding: '12px 18px',
                  background: 'var(--surface)',
                  borderBottom: '1px solid var(--border)'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ fontWeight: 800, fontSize: '14px', color: 'var(--text)' }}>
                    {category.name}
                  </span>
                  <span className="tag plain" style={{ fontWeight: 700, fontSize: '10.5px' }}>
                    {items.length} {items.length === 1 ? 'Detection' : 'Detections'}
                  </span>
                </div>
                <div style={{ fontSize: '11.5px', color: 'var(--text-faint)', marginTop: '2px' }}>
                  {category.description}
                </div>
              </div>

              {/* Section Cards */}
              <div style={{ padding: '16px', background: 'var(--bg0)' }}>
                <div className="cards-grid" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(310px, 1fr))', gap: '14px' }}>
                  {items.map(renderInsightCard)}
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : (
        /* When a specific domain is selected from dropdown: Clean grid */
        <div className="cards-grid" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(310px, 1fr))', gap: '14px' }}>
          {filteredInsights.map(renderInsightCard)}
        </div>
      )}

      {/* Forensic Evidence Details Modal (No icons) */}
      {selectedInsight && (
        <div className="modal-overlay open" onClick={() => setSelectedInsight(null)}>
          <div className="modal" onClick={(e: React.MouseEvent<HTMLDivElement>) => e.stopPropagation()} style={{ maxWidth: '640px' }}>
            <button className="close neu-btn ghost" onClick={() => setSelectedInsight(null)} style={{ float: 'right' }}>
              ✕
            </button>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '10px' }}>
              <span className={`tag ${(selectedInsight.severity || 'med').toLowerCase()}`} style={{ fontSize: '11px' }}>
                {esc(selectedInsight.severity)}
              </span>
              <span className="tag plain mono" style={{ fontSize: '11px' }}>
                {INSIGHT_TYPE_LABELS[selectedInsight.insight_type || ''] || esc(selectedInsight.insight_type)} · {esc(selectedInsight.insight_id)}
              </span>
            </div>

            <h3 style={{ fontWeight: 800, fontSize: '17px', color: 'var(--text)', marginBottom: '8px' }}>
              {renderInlineMarkdown(esc(selectedInsight.title))}
            </h3>

            <div style={{ fontSize: '13.5px', color: 'var(--text-dim)', marginBottom: '16px', lineHeight: 1.55 }}>
              {renderInlineMarkdown(esc(selectedInsight.derived_interpretation))}
            </div>

            {/* Observed Graph Facts */}
            <div style={{ fontWeight: 700, fontSize: '12.5px', textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--text-dim)', marginBottom: '8px' }}>
              Observed Graph Facts
            </div>
            {(selectedInsight.observed_facts || []).map((f, idx) => (
              <div key={idx} style={{ fontSize: '12.5px', color: 'var(--text)', marginBottom: '6px', display: 'flex', gap: '8px', lineHeight: 1.45 }}>
                <span style={{ color: 'var(--text-faint)' }}>-</span>
                <div>{renderInlineMarkdown(esc(f))}</div>
              </div>
            ))}

            {/* Alternative Explanations */}
            {(selectedInsight.alternative_explanations || []).length > 0 && (
              <React.Fragment>
                <div style={{ fontWeight: 700, fontSize: '12.5px', textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--text-dim)', margin: '16px 0 8px' }}>
                  Alternative Explanations (Bias Safeguards)
                </div>
                {selectedInsight.alternative_explanations?.map((a, idx) => (
                  <div key={idx} style={{ fontSize: '12px', color: 'var(--text-faint)', marginBottom: '4px', lineHeight: 1.4 }}>
                    - {esc(a)}
                  </div>
                ))}
              </React.Fragment>
            )}

            {/* Entities Involved */}
            {(selectedInsight.entities_involved || []).length > 0 && (
              <div style={{ marginTop: '14px', paddingTop: '12px', borderTop: '1px solid var(--border)' }}>
                <div style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-faint)', textTransform: 'uppercase', marginBottom: '6px' }}>
                  Entities Involved
                </div>
                <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                  {selectedInsight.entities_involved?.map(ent => (
                    <span key={ent} className="tag plain mono" style={{ fontSize: '10.5px' }}>
                      {esc(ent)}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Legal Disclaimer */}
            <div
              style={{
                marginTop: '18px',
                padding: '10px 14px',
                borderRadius: '8px',
                background: 'var(--bg0)',
                border: '1px solid var(--border)',
                fontSize: '11px',
                color: 'var(--text-faint)',
                lineHeight: 1.4
              }}
            >
              {esc(selectedInsight.disclaimer || 'Intelligence alert generated automatically from graph topology.')}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
