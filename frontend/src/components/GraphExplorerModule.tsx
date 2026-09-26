import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import * as vis from 'vis-network/standalone';
import { API, esc, LABEL_COLOR, getNodeLevel, getDeterministicSeed, Case, GraphNode, GraphEdge, AiChatMessage, ThemeMode } from '../services/api';
import { FormattedAiMessage } from './FormattedAiMessage';
import { EntityPropertiesTable } from './EntityPropertiesTable';

export interface GraphExplorerModuleProps {
  cases: Case[];
  selectedCase: string | null;
  setSelectedCase: (id: string | null) => void;
  openEntityModal: (id: string) => void;
  addToast: (msg: string, type?: string) => void;
  theme: string;
}

export function GraphExplorerModule({ cases, selectedCase, setSelectedCase, openEntityModal, addToast, theme }: GraphExplorerModuleProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const networkRef = useRef<any>(null);
  const [caseFilter, setCaseFilter] = useState<string>(selectedCase || '');
  const [graphType, setGraphType] = useState<string>('all');
  const [layoutType, setLayoutType] = useState<string>('structured');
  const [edgeLabelMode, setEdgeLabelMode] = useState<string>('clean');
  const [limit, setLimit] = useState<number>(1200);
  const [hideIsolated, setHideIsolated] = useState<boolean>(false);
  const [hideCaseLinks, setHideCaseLinks] = useState<boolean>(true);
  const [physicsEnabled, setPhysicsEnabled] = useState<boolean>(true);
  const [aiPanelCollapsed, setAiPanelCollapsed] = useState<boolean>(false);
  const [graphNodes, setGraphNodes] = useState<GraphNode[]>([]);
  const [graphEdges, setGraphEdges] = useState<GraphEdge[]>([]);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [loading, setLoading] = useState<boolean>(false);

  // AI Copilot state
  const [aiChatLog, setAiChatLog] = useState<AiChatMessage[]>([
    {
      sender: 'bot',
      model: 'Atlas AI Graph Extractor',
      content: "How can I assist your investigation?",
      chips: [
        'Who is the main suspect?'
      ]
    }
  ]);
  const [aiInput, setAiInput] = useState<string>('');
  const [aiQuerying, setAiQuerying] = useState<boolean>(false);

  const fetchGraph = useCallback(async () => {
    setLoading(true);
    try {
      const url = `/api/graph?limit=${limit}&graph_type=${encodeURIComponent(graphType)}${caseFilter ? `&case_id=${encodeURIComponent(caseFilter)}` : ''}`;
      const g = await API.get<{ nodes?: GraphNode[]; edges?: GraphEdge[] }>(url);
      setGraphNodes(g.nodes || []);
      setGraphEdges(g.edges || []);
    } catch (e: any) {
      addToast(`Failed to load graph: ${e.message}`, 'err');
    } finally {
      setLoading(false);
    }
  }, [limit, graphType, caseFilter, addToast]);

  useEffect(() => {
    fetchGraph();
  }, [fetchGraph]);

  useEffect(() => {
    setCaseFilter(selectedCase || '');
  }, [selectedCase]);

  // Render Network Graph
  useEffect(() => {
    if (!containerRef.current) return;
    if (networkRef.current) {
      networkRef.current.destroy();
      networkRef.current = null;
    }

    const isLight = theme === 'light';
    const textColor = isLight ? '#0f172a' : '#cbd5e1';
    const edgeColor = isLight ? 'rgba(148, 163, 184, 0.55)' : 'rgba(100, 116, 139, 0.45)';

    // Compute degrees
    const degrees: Record<string, number> = {};
    (graphEdges || []).forEach(e => {
      degrees[e.source] = (degrees[e.source] || 0) + 1;
      degrees[e.target] = (degrees[e.target] || 0) + 1;
    });

    const seenNodeIds = new Set<string>();
    const nodes: any[] = [];
    (graphNodes || []).forEach(n => {
      if (!n || !n.id || seenNodeIds.has(n.id)) return;
      if (hideIsolated && (degrees[n.id] || 0) <= 1 && !n.labels?.includes('Case')) return;

      seenNodeIds.add(n.id);
      const isCase = n.labels?.includes('Case');
      const isPerson = n.labels?.includes('Person');
      const isPhone = n.labels?.includes('Phone');
      const isTower = n.labels?.includes('CellTower');

      let nodeSize = 22;
      let nodeShape = 'dot';
      let nodeBg = (n.labels?.[0] && LABEL_COLOR[n.labels[0]]) || '#94a3b8';

      if (graphType === 'cdr') {
        if (isPhone) { nodeSize = 28; nodeBg = '#f97316'; }
        else if (isTower) { nodeSize = 28; nodeShape = 'triangle'; nodeBg = '#06b6d4'; }
      } else if (graphType === 'person') {
        nodeSize = isPerson ? 30 : (isPhone ? 24 : 22);
        if (isPerson) nodeBg = '#3b82f6';
      } else if (graphType === 'financial') {
        nodeSize = n.labels?.includes('BankAccount') ? 28 : 22;
        if (n.labels?.includes('BankAccount')) nodeBg = '#10b981';
      } else {
        if (isCase) {
          nodeSize = 32;
          nodeBg = '#6366f1';
        } else if (isPerson) {
          nodeSize = 26;
          nodeBg = '#3b82f6';
        } else if (isPhone) {
          nodeSize = 24;
          nodeBg = '#f97316';
        } else if (n.labels?.includes('BankAccount')) {
          nodeSize = 24;
          nodeBg = '#10b981';
        } else if (n.labels?.includes('Vehicle')) {
          nodeSize = 24;
          nodeBg = '#ec4899';
        } else if (isTower) {
          nodeSize = 26;
          nodeShape = 'triangle';
          nodeBg = '#06b6d4';
        } else if (n.labels?.includes('Location')) {
          nodeSize = 24;
          nodeBg = '#84cc16';
        } else if (n.labels?.includes('SocialHandle')) {
          nodeSize = 22;
          nodeBg = '#8b5cf6';
        } else if (n.labels?.includes('IPAddress')) {
          nodeSize = 22;
          nodeBg = '#f43f5e';
        } else if (n.labels?.includes('SourceRecord') || n.labels?.includes('Document')) {
          nodeSize = 20;
          nodeBg = '#64748b';
        } else {
          nodeSize = 22;
        }
      }

      // Resolve associated person for phone if present
      let associatedPerson = (n.properties?.associated_person_name || n.properties?.registered_owner || n.properties?.subscriber_name || n.properties?.owner_name) as string | undefined;
      let associatedPersonId = (n.properties?.associated_person_id || n.properties?.owner_person_id) as string | undefined;

      if (isPhone && !associatedPerson) {
        // Search graph edges for an owner link
        const ownerEdge = (graphEdges || []).find(e =>
          (e.type === 'OWNS' || e.type === 'USES' || e.type === 'HAS_PHONE') &&
          (e.target === n.id || e.source === n.id)
        );
        if (ownerEdge) {
          const pId = ownerEdge.target === n.id ? ownerEdge.source : ownerEdge.target;
          const pNode = (graphNodes || []).find(x => x.id === pId);
          if (pNode && pNode.labels?.includes('Person')) {
            associatedPerson = (pNode.properties?.name || pNode.name || pId) as string;
            associatedPersonId = pId;
          }
        }
      }

      let nodeLabel = n.name || n.id;
      if (isPhone && associatedPerson && String(associatedPerson).toLowerCase() !== 'unknown') {
        const rawPhone = String(n.properties?.phone_number || n.name?.split('\n')[0] || n.id).trim();
        const cleanPerson = String(associatedPerson).split('\n')[0].replace(/^\(|\)$/g, '').trim();
        nodeLabel = `${rawPhone}\n(${cleanPerson})`;
      }

      // Build rich hover tooltip with entity metadata and communication breakdown
      const tooltipLines: string[] = [
        `📌 ${n.labels?.join(', ') || 'Entity'}: ${nodeLabel.replace('\n', ' ')}`,
        `ID: ${n.id}`
      ];
      if (isPhone && associatedPerson && String(associatedPerson).toLowerCase() !== 'unknown') {
        tooltipLines.push(`👤 Associated Person: ${String(associatedPerson).split('\n')[0].replace(/^\(|\)$/g, '').trim()}`);
      }
      if (n.properties?.role) tooltipLines.push(`Role: ${n.properties.role}`);
      if (n.properties?.phone_number && n.properties.phone_number !== n.name) tooltipLines.push(`Phone: ${n.properties.phone_number}`);
      if (n.properties?.risk_score !== undefined) tooltipLines.push(`Risk Score: ${n.properties.risk_score}`);

      const comms = n.properties?.communications;
      const totalCalls = Number(n.properties?.total_calls || 0);
      if (totalCalls > 0) {
        tooltipLines.push(`\n📞 Total Calls Logged: ${totalCalls}`);
      }
      if (comms && typeof comms === 'object') {
        const commList = Object.values(comms) as any[];
        if (commList.length > 0) {
          tooltipLines.push(`📞 Communication Breakdown:`);
          commList.slice(0, 10).forEach(c => {
            const partner = c.partner_name || c.partner_id;
            const cCount = Number(c.call_count || 1);
            const dur = c.summary ? ` (${c.summary})` : '';
            tooltipLines.push(`  • ${partner}: ${cCount} time${cCount > 1 ? 's' : ''}${dur}`);
          });
          if (commList.length > 10) {
            tooltipLines.push(`  • ...and ${commList.length - 10} more contacts`);
          }
        }
      }

      const txs = n.properties?.transactions;
      const totalTx = Number(n.properties?.total_transactions || 0);
      const totalAmt = Number(n.properties?.total_amount_transferred || 0);
      if (totalTx > 0) {
        tooltipLines.push(`\n💳 Total Transactions: ${totalTx}${totalAmt > 0 ? ` (₹${Math.round(totalAmt).toLocaleString()})` : ''}`);
      }
      if (txs && typeof txs === 'object') {
        const txList = Object.values(txs) as any[];
        if (txList.length > 0) {
          tooltipLines.push(`💳 Transaction Breakdown:`);
          txList.slice(0, 10).forEach(t => {
            const partner = t.partner_name || t.partner_id;
            const tCount = Number(t.tx_count || 1);
            const amtStr = t.summary ? ` (${t.summary})` : (t.total_amount ? ` [₹${Math.round(t.total_amount).toLocaleString()}]` : '');
            tooltipLines.push(`  • ${partner}: ${tCount} txn${tCount > 1 ? 's' : ''}${amtStr}`);
          });
          if (txList.length > 10) {
            tooltipLines.push(`  • ...and ${txList.length - 10} more accounts`);
          }
        }
      }

      const fontSize = isCase ? 15 : (isPerson ? 14 : (isPhone ? 13 : 12.5));

      nodes.push({
        id: n.id,
        label: nodeLabel,
        level: getNodeLevel(n.labels),
        title: tooltipLines.join('\n'),
        shape: nodeShape,
        size: nodeSize,
        borderWidth: isCase ? 3.5 : 2.5,
        borderWidthSelected: 4.5,
        shadow: {
          enabled: true,
          color: isLight ? 'rgba(15, 23, 42, 0.12)' : 'rgba(0, 0, 0, 0.55)',
          size: 6,
          x: 2,
          y: 2
        },
        color: {
          background: nodeBg,
          border: isLight ? '#ffffff' : '#0f172a',
          highlight: { background: nodeBg, border: isLight ? '#1d4ed8' : '#38bdf8' },
          hover: { background: nodeBg, border: isLight ? '#1d4ed8' : '#38bdf8' }
        },
        font: {
          color: isLight ? '#0f172a' : '#f8fafc',
          size: fontSize,
          face: 'Inter, system-ui, -apple-system, sans-serif',
          vadjust: 4,
          strokeWidth: isLight ? 4 : 2.5,
          strokeColor: isLight ? '#ffffff' : '#0f172a'
        }
      });
    });

    const seenEdgeIds = new Set<string>();
    const edges: any[] = [];
    (graphEdges || []).forEach((e, idx) => {
      if (!e || !e.source || !e.target) return;
      if (!seenNodeIds.has(e.source) || !seenNodeIds.has(e.target)) return;

      let edgeId = String(e.id || `edge_${e.source}_${e.type}_${e.target}_${idx}`);
      if (seenEdgeIds.has(edgeId)) edgeId = `${edgeId}_${idx}`;
      seenEdgeIds.add(edgeId);

      const isCaseLink = e.type === 'INVOLVES';
      if (hideCaseLinks && isCaseLink) return;

      const callCount = Number(e.properties?.call_count || 0);
      const txCount = Number(e.properties?.tx_count || 0);
      let label = e.type || '';
      if (e.properties?.summary) {
        label = String(e.properties.summary);
      } else if (callCount > 1) {
        label = `${callCount} calls`;
      } else if (txCount > 1) {
        label = `${txCount} txns`;
      }
      if (edgeLabelMode === 'none') label = '';
      else if (edgeLabelMode === 'clean' && isCaseLink) label = '';

      // Detailed edge tooltip
      let edgeTitle = `${e.type || 'LINK'} (${e.source} → ${e.target})`;
      if (callCount > 1) {
        edgeTitle += `\n📞 Aggregated Calls: ${callCount} times`;
        if (e.properties?.total_duration) {
          edgeTitle += `\n⏱ Total Duration: ${e.properties.total_duration}`;
        }
      } else if (txCount > 1) {
        edgeTitle += `\n💳 Aggregated Transactions: ${txCount} times`;
        if (e.properties?.total_amount) {
          edgeTitle += `\n💰 Total Transferred: ₹${Math.round(Number(e.properties.total_amount)).toLocaleString()}`;
        }
      } else if (e.properties?.summary) {
        edgeTitle += `\n${e.properties.summary}`;
      } else if (e.properties?.duration_seconds) {
        edgeTitle += `\nDuration: ${e.properties.duration_seconds}s`;
      } else if (e.properties?.amount) {
        edgeTitle += `\nAmount: ₹${Math.round(Number(e.properties.amount)).toLocaleString()}`;
      }

      // Keep edges sleek, clear and crisp
      let edgeWidth = 1.3;
      if (callCount > 1) {
        edgeWidth = Math.min(1.5 + Math.log2(callCount) * 0.3, 2.8);
      } else if (txCount > 1) {
        edgeWidth = Math.min(1.5 + Math.log2(txCount) * 0.3, 2.8);
      }

      edges.push({
        id: edgeId,
        from: e.source,
        to: e.target,
        label: label,
        title: edgeTitle,
        width: edgeWidth,
        selectionWidth: 2.0,
        hoverWidth: 2.0,
        physics: !isCaseLink,
        arrows: {
          to: {
            enabled: true,
            scaleFactor: 0.6
          }
        },
        color: {
          color: isCaseLink
            ? (isLight ? 'rgba(2, 132, 199, 0.45)' : 'rgba(56, 189, 248, 0.45)')
            : (graphType === 'person' ? '#93c5fd' : edgeColor),
          highlight: isLight ? '#0284c7' : '#38bdf8',
          hover: isLight ? '#0284c7' : '#38bdf8'
        },
        dashes: isCaseLink,
        font: {
          color: isLight ? '#1e293b' : '#e2e8f0',
          size: 10,
          face: 'Inter, system-ui, sans-serif',
          strokeWidth: isLight ? 2 : 0,
          strokeColor: isLight ? '#ffffff' : 'transparent',
          background: isLight ? 'rgba(255, 255, 255, 0.94)' : 'rgba(15, 23, 42, 0.94)',
          align: 'horizontal'
        },
        smooth: { enabled: true, type: 'curvedCW', roundness: 0.15 }
      });
    });

    const seed = getDeterministicSeed(caseFilter || 'all');
    let layoutOpts: any = { randomSeed: seed };
    let physicsOpts: any = {};

    if (layoutType === 'hierarchy_ud') {
      layoutOpts.hierarchical = { enabled: true, direction: 'UD', sortMethod: 'directed', levelSeparation: 220, nodeSpacing: 240 };
      physicsOpts = { enabled: physicsEnabled, solver: 'hierarchicalRepulsion', hierarchicalRepulsion: { nodeDistance: 240, centralGravity: 0.0, springLength: 180, springConstant: 0.04, damping: 0.55 } };
    } else if (layoutType === 'hierarchy_lr') {
      layoutOpts.hierarchical = { enabled: true, direction: 'LR', sortMethod: 'directed', levelSeparation: 240, nodeSpacing: 220 };
      physicsOpts = { enabled: physicsEnabled, solver: 'hierarchicalRepulsion', hierarchicalRepulsion: { nodeDistance: 220, centralGravity: 0.0, springLength: 180, springConstant: 0.04, damping: 0.55 } };
    } else if (layoutType === 'radial') {
      layoutOpts.improvedLayout = true;
      physicsOpts = { enabled: physicsEnabled, solver: 'forceAtlas2Based', forceAtlas2Based: { gravitationalConstant: -150, centralGravity: 0.005, springLength: 260, springConstant: 0.035, damping: 0.65, avoidOverlap: 1.0 } };
    } else {
      layoutOpts.improvedLayout = true;
      physicsOpts = { enabled: physicsEnabled, solver: 'forceAtlas2Based', forceAtlas2Based: { gravitationalConstant: -140, centralGravity: 0.003, springLength: 240, springConstant: 0.035, damping: 0.65, avoidOverlap: 1.0 } };
    }

    const net = new vis.Network(containerRef.current, { nodes, edges }, {
      layout: layoutOpts,
      physics: {
        ...physicsOpts,
        stabilization: {
          enabled: true,
          iterations: 150,
          updateInterval: 25,
          fit: true
        }
      },
      nodes: { borderWidth: 2.5 },
      edges: { width: 1.3, selectionWidth: 2.0, hoverWidth: 2.0 },
      interaction: { hover: true, tooltipDelay: 100, navigationButtons: true, keyboard: true, zoomView: true, dragView: true }
    });

    net.on('click', (p: any) => {
      if (p.nodes && p.nodes.length) {
        const targetId = p.nodes[0];
        const nObj = graphNodes.find(n => n.id === targetId);
        if (nObj) setSelectedNode(nObj);
      }
    });

    net.once('stabilizationIterationsDone', () => {
      // Keep physics alive with gentle forces for continuous to-and-fro oscillation
      if (physicsEnabled) {
        net.setOptions({ physics: { enabled: true, solver: 'forceAtlas2Based', forceAtlas2Based: { gravitationalConstant: -35, centralGravity: 0.002, springLength: 220, springConstant: 0.012, damping: 0.45, avoidOverlap: 1.0 }, maxVelocity: 8, minVelocity: 0.3 } });
      }
    });
    net.once('stabilized', () => {
      // Keep physics alive with gentle forces for continuous to-and-fro oscillation
      if (physicsEnabled) {
        net.setOptions({ physics: { enabled: true, solver: 'forceAtlas2Based', forceAtlas2Based: { gravitationalConstant: -35, centralGravity: 0.002, springLength: 220, springConstant: 0.012, damping: 0.45, avoidOverlap: 1.0 }, maxVelocity: 8, minVelocity: 0.3 } });
      }
    });

    networkRef.current = net;

    return () => {
      if (net) net.destroy();
      networkRef.current = null;
    };
  }, [graphNodes, graphEdges, graphType, layoutType, edgeLabelMode, hideIsolated, hideCaseLinks, physicsEnabled, theme, caseFilter]);

  const handleAiQuerySubmit = async (e?: React.FormEvent | null, promptOverride: string | null = null) => {
    if (e && e.preventDefault) e.preventDefault();
    const q = promptOverride || aiInput.trim();
    if (!q) return;

    if (!promptOverride) setAiInput('');
    setAiChatLog(prev => [...prev, { sender: 'user', content: q }]);
    setAiQuerying(true);

    // Client-side extraction intent detection for instant responsiveness
    const qLower = q.toLowerCase();
    let clientDetected: string | null = null;
    if (qLower.includes('cdr') || qLower.includes('call') || qLower.includes('phone graph') || qLower.includes('telecom')) {
      clientDetected = 'cdr';
    } else if (qLower.includes('person') || qLower.includes('suspect') || qLower.includes('people') || qLower.includes('connecting person')) {
      clientDetected = 'person';
    } else if (qLower.includes('financial') || qLower.includes('money') || qLower.includes('bank') || qLower.includes('transfer')) {
      clientDetected = 'financial';
    } else if (qLower.includes('all') || qLower.includes('full graph') || qLower.includes('reset') || qLower.includes('entire graph')) {
      clientDetected = 'all';
    }

    if (clientDetected && clientDetected !== graphType) {
      setGraphType(clientDetected);
      addToast(
        clientDetected === 'cdr' ? 'AI Extractor: Switched view to CDR telecommunications only' :
        clientDetected === 'person' ? 'AI Extractor: Switched view to Person-to-Person syndicate only' :
        clientDetected === 'financial' ? 'AI Extractor: Switched view to Financial money flow only' :
        'AI Extractor: Restored full ecosystem graph',
        'ok'
      );
    }

    try {
      const res = await API.post<{ ai_model?: string; answer?: string; extracted_graph_type?: string }>('/api/graph/ai-query', {
        question: q,
        case_id: caseFilter || null,
        nodes_count: graphNodes?.length || null,
        edges_count: graphEdges?.length || null,
        selected_node_id: selectedNode?.id || null
      });

      if (res.extracted_graph_type && res.extracted_graph_type !== graphType && res.extracted_graph_type !== clientDetected) {
        setGraphType(res.extracted_graph_type);
      }

      setAiChatLog(prev => [...prev, {
        sender: 'bot',
        model: res.ai_model || 'Atlas AI Graph Extractor',
        content: res.answer || 'No specific inference generated.',
        chips: [
          'Who is the main suspect?'
        ]
      }]);
    } catch (err: any) {
      setAiChatLog(prev => [...prev, {
        sender: 'bot',
        error: true,
        content: `Inference query error: ${err.message}`
      }]);
    } finally {
      setAiQuerying(false);
    }
  };

  const nodeCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    (graphNodes || []).forEach(n => {
      const l = n.labels?.[0] || 'Entity';
      counts[l] = (counts[l] || 0) + 1;
    });
    return counts;
  }, [graphNodes]);

  return (
    <div>
      <div className="card">
        <div className="card-header flex items-center justify-between gap-3 flex-wrap">
          <div className="card-title font-semibold">
            Network Topology Explorer
          </div>
          <div className="row flex items-end gap-2 flex-wrap" style={{gap:'6px', alignItems:'flex-end', flexWrap:'wrap'}}>
            <div className="field" style={{minWidth:'150px'}}>
              <label>Case Filter</label>
              <select className="control" value={caseFilter} onChange={(e: React.ChangeEvent<HTMLSelectElement>) => { setCaseFilter(e.target.value); setSelectedCase(e.target.value || null); }}>
                <option value="">All Ingested Cases</option>
                {cases.map(c => <option key={c.case_id} value={c.case_id}>{esc(c.case_name || c.case_id)}</option>)}
              </select>
            </div>

            <div className="field" style={{minWidth:'140px'}}>
              <label>Layout Structure</label>
              <select className="control" value={layoutType} onChange={(e: React.ChangeEvent<HTMLSelectElement>) => setLayoutType(e.target.value)}>
                <option value="structured">Structured Organic</option>
                <option value="hierarchy_ud">Hierarchical Flow (Top-to-Bottom)</option>
                <option value="hierarchy_lr">Pipeline Flow (Left-to-Right)</option>
                <option value="radial">Central Core & Radial Orbit</option>
              </select>
            </div>
            <div className="field" style={{maxWidth:'110px'}}>
              <label>Edge Labels</label>
              <select className="control" value={edgeLabelMode} onChange={(e: React.ChangeEvent<HTMLSelectElement>) => setEdgeLabelMode(e.target.value)}>
                <option value="clean">Clean (Hide INVOLVES)</option>
                <option value="all">Show All</option>
                <option value="none">No Edge Text</option>
              </select>
            </div>
            <div className="flex gap-1.5 items-end" style={{display:'flex', gap:'6px', alignItems:'flex-end'}}>
              <button className="neu-btn primary transition hover:opacity-90" disabled={loading} onClick={fetchGraph} style={{padding:'5px 12px', fontSize:'11.5px'}}>{loading ? 'Rendering…' : 'Render'}</button>
              <button className="neu-btn ghost transition" onClick={() => setAiPanelCollapsed(prev => !prev)} style={{display:'inline-flex', alignItems:'center', gap:'5px', color:'var(--accent)', padding:'5px 10px', fontSize:'11.5px'}}>
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="m12 3-1.9 5.8a2 2 0 0 1-1.3 1.3L3 12l5.8 1.9a2 2 0 0 1 1.3 1.3L12 21l1.9-5.8a2 2 0 0 1 1.3-1.3L21 12l-5.8-1.9a2 2 0 0 1-1.3-1.3Z"/></svg>
                <span>{aiPanelCollapsed ? 'Show Copilot' : 'AI Copilot'}</span>
              </button>
              <button className="neu-btn ghost transition" onClick={() => { setPhysicsEnabled(p => !p); addToast(physicsEnabled ? 'Physics locked into place' : 'Physics simulation resumed', 'info'); }} style={{padding:'5px 10px', fontSize:'11.5px'}}>
                <span>{physicsEnabled ? 'Pause' : 'Live Bounce'}</span>
              </button>
            </div>
          </div>
        </div>

        <div className="flex items-center justify-between gap-3 mb-2 flex-wrap" style={{display:'flex', alignItems:'center', justifyContent:'space-between', gap:'10px', marginBottom:'10px', flexWrap:'wrap'}}>
          <div className="flex items-center gap-2 flex-wrap" style={{display:'flex', alignItems:'center', gap:'6px', flexWrap:'wrap'}}>
            <span className="text-xs font-bold uppercase tracking-wider" style={{color:'var(--text-faint)', fontSize:'10px', fontWeight:700}}>Quick Extract:</span>
            <div style={{display:'inline-flex', background:'var(--bg1)', border:'1px solid var(--border)', borderRadius:'6px', padding:'2px', gap:'2px'}}>
              <button
                type="button"
                className={`neu-btn ghost ${graphType === 'all' ? 'active' : ''}`}
                style={{padding:'3px 9px', fontSize:'10.5px', borderRadius:'4px', fontWeight:600, background: graphType === 'all' ? 'var(--accent)' : 'transparent', color: graphType === 'all' ? '#ffffff' : 'var(--text)'}}
                onClick={() => { setGraphType('all'); addToast('Showing full ecosystem graph', 'info'); }}
              >
                Full
              </button>
              <button
                type="button"
                className={`neu-btn ghost ${graphType === 'cdr' ? 'active' : ''}`}
                style={{padding:'3px 9px', fontSize:'10.5px', borderRadius:'4px', fontWeight:600, background: graphType === 'cdr' ? 'var(--accent)' : 'transparent', color: graphType === 'cdr' ? '#ffffff' : 'var(--text)'}}
                onClick={() => { setGraphType('cdr'); addToast('Extracted CDR telecommunications graph', 'ok'); }}
              >
                CDR Only
              </button>
              <button
                type="button"
                className={`neu-btn ghost ${graphType === 'person' ? 'active' : ''}`}
                style={{padding:'3px 9px', fontSize:'10.5px', borderRadius:'4px', fontWeight:600, background: graphType === 'person' ? 'var(--accent)' : 'transparent', color: graphType === 'person' ? '#ffffff' : 'var(--text)'}}
                onClick={() => { setGraphType('person'); addToast('Extracted Person-to-Person syndicate graph', 'ok'); }}
              >
                Person Only
              </button>
              <button
                type="button"
                className={`neu-btn ghost ${graphType === 'financial' ? 'active' : ''}`}
                style={{padding:'3px 9px', fontSize:'10.5px', borderRadius:'4px', fontWeight:600, background: graphType === 'financial' ? 'var(--accent)' : 'transparent', color: graphType === 'financial' ? '#ffffff' : 'var(--text)'}}
                onClick={() => { setGraphType('financial'); addToast('Extracted Financial flow graph', 'ok'); }}
              >
                Financial Only
              </button>
            </div>
            <label className="inline-flex items-center gap-1 cursor-pointer text-xs ml-2" style={{display:'inline-flex', alignItems:'center', gap:'5px', fontSize:'11px', color:'var(--text-dim)', cursor:'pointer', marginLeft:'6px'}}>
              <input type="checkbox" checked={hideIsolated} onChange={(e: React.ChangeEvent<HTMLInputElement>) => setHideIsolated(e.target.checked)} style={{cursor:'pointer'}} />
              Hide Isolated
            </label>
            <label className="inline-flex items-center gap-1 cursor-pointer text-xs ml-2" style={{display:'inline-flex', alignItems:'center', gap:'5px', fontSize:'11px', color: hideCaseLinks ? 'var(--accent)' : 'var(--text-dim)', cursor:'pointer', marginLeft:'6px'}} title="Hides the radial starburst of dashed case links so that actual transaction and call paths are completely unobstructed">
              <input type="checkbox" checked={hideCaseLinks} onChange={(e: React.ChangeEvent<HTMLInputElement>) => setHideCaseLinks(e.target.checked)} style={{cursor:'pointer'}} />
              Hide Case Spokes (Clean Network)
            </label>
          </div>
          <div className="text-xs" style={{fontSize:'10.5px', color:'var(--text-dim)'}}>
            {graphType === 'cdr' ? 'Filtered: Telephone calls & Cell Towers only (unrelated entities hidden)' :
             graphType === 'person' ? 'Filtered: Person syndicate members & direct linkages only' :
             graphType === 'financial' ? 'Filtered: Bank accounts & money transfer routes only' :
             'Full Graph: Drag nodes to inspect · Or ask AI Copilot e.g. "extract only CDR graph"'}
          </div>
        </div>

        <div id="graph">
          {loading && (
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-3.5 z-10" style={{position:'absolute', inset:0, display:'flex', flexDirection:'column', alignItems:'center', justifyContent:'center', gap:'14px', color:'var(--text-dim)', background:'var(--graph-bg)', zIndex:10}}>
              <div className="status-dot" style={{width:'14px', height:'14px', background:'var(--accent)', animation:'pulse 1s infinite'}}></div>
              <div style={{fontSize:'13px'}}>Generating graph layout…</div>
            </div>
          )}
          <div id="graphCanvas" ref={containerRef}></div>

          {/* AI Copilot Side Structure */}
          <div className={`graph-ai-box ${aiPanelCollapsed ? 'collapsed' : ''}`}>
            <div className="graph-ai-header flex items-center justify-between">
              <div className="flex items-center gap-1.5" style={{display:'flex', alignItems:'center', gap:'7px'}}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth="2"><path d="m12 3-1.9 5.8a2 2 0 0 1-1.3 1.3L3 12l5.8 1.9a2 2 0 0 1 1.3 1.3L12 21l1.9-5.8a2 2 0 0 1 1.3-1.3L21 12l-5.8-1.9a2 2 0 0 1-1.3-1.3Z"/></svg>
                <span className="font-bold text-xs" style={{fontWeight:700, fontSize:'13px', color:'var(--text)'}}>AI Copilot</span>
                <span className="tag open" style={{padding:'1px 6px', fontSize:'9.5px', textTransform:'uppercase'}}>AI Inference</span>
              </div>
              <button className="neu-btn ghost transition" style={{padding:'2px 7px', fontSize:'11px'}} onClick={() => setAiPanelCollapsed(true)}>✕</button>
            </div>

            <div className="graph-ai-body">
              {aiChatLog.map((msg, idx) => (
                <div key={idx} className={`ai-msg ${msg.sender === 'user' ? 'user' : 'bot'}`} style={msg.error ? {borderColor:'rgba(239, 68, 68, 0.4)'} : {}}>
                  <div className="ai-msg-hdr flex items-center gap-1.5">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="m12 3-1.9 5.8a2 2 0 0 1-1.3 1.3L3 12l5.8 1.9a2 2 0 0 1 1.3 1.3L12 21l1.9-5.8a2 2 0 0 1 1.3-1.3L21 12l-5.8-1.9a2 2 0 0 1-1.3-1.3Z"/></svg>
                    <span>{msg.sender === 'user' ? 'Investigator Query' : (msg.model || 'AI Copilot')}</span>
                  </div>
                  {msg.sender === 'user' ? (
                    <div style={{ color: 'var(--text)' }}>{msg.content}</div>
                  ) : (
                    <FormattedAiMessage content={msg.content} />
                  )}
                  {msg.chips && (
                    <div className="ai-quick-chips flex flex-wrap gap-1.5 mt-2">
                      {msg.chips.map((c, cIdx) => (
                        <button key={cIdx} type="button" className="ai-chip transition" onClick={() => handleAiQuerySubmit(null, c.replace(/^[^a-zA-Z0-9]+/, ''))}>
                          {c}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              ))}
              {aiQuerying && (
                <div className="ai-msg bot">
                  <div className="ai-msg-hdr flex items-center gap-1.5">
                    <div className="status-dot" style={{width:'8px', height:'8px', background:'var(--accent)', animation:'pulse 1s infinite'}}></div>
                    <span>AI is analyzing topology…</span>
                  </div>
                  <div style={{fontSize:'11.5px', color:'var(--text-faint)'}}>Correlating nodes, transactions, and hidden links</div>
                </div>
              )}
            </div>

            <div className="graph-ai-footer">
              <form onSubmit={handleAiQuerySubmit} className="flex gap-1.5 w-full m-0" style={{display:'flex', gap:'6px', width:'100%', margin:0}}>
                <input type="text" className="control" style={{fontSize:'12px', padding:'7px 10px', flex:1}} placeholder="Ask about this network…" value={aiInput} onChange={(e: React.ChangeEvent<HTMLInputElement>) => setAiInput(e.target.value)} />
                <button type="submit" className="neu-btn primary transition" disabled={aiQuerying} style={{padding:'0 12px', fontSize:'12px'}}>{aiQuerying ? '…' : 'Ask'}</button>
              </form>
            </div>
          </div>
        </div>

        <div className="legend flex flex-wrap gap-3">
          {Object.entries(nodeCounts).map(([k, v]) => (
            <div key={k} className="lg flex items-center gap-1.5">
              <span className="dot" style={{background: LABEL_COLOR[k] || '#94a3b8'}}></span>
              <b>{k}</b> <span className="mono">({v})</span>
            </div>
          ))}
        </div>
        <div style={{marginTop:'14px', fontSize:'13px', color:'var(--text-dim)', fontFamily:'var(--mono)'}}>
          Subnetwork: <b>{graphNodes.length}</b> nodes · <b>{graphEdges.length}</b> edges · Seed: <span className="mono">{getDeterministicSeed(caseFilter || 'all')}</span>
        </div>
      </div>

      {selectedNode && (
        <div className="card">
          <div className="card-header flex items-center justify-between gap-3 flex-wrap">
            <div className="card-title font-semibold">Entity Inspection</div>
            <button className="neu-btn ghost transition" onClick={() => setSelectedNode(null)}>Close</button>
          </div>
          <div>
            {(() => {
              const isSelectedPhone = selectedNode.labels?.includes('Phone');
              let selectedPhoneOwner = (selectedNode.properties?.associated_person_name || selectedNode.properties?.registered_owner || selectedNode.properties?.subscriber_name || selectedNode.properties?.owner_name) as string | undefined;
              let selectedPhoneOwnerId = (selectedNode.properties?.associated_person_id || selectedNode.properties?.owner_person_id) as string | undefined;

              if (isSelectedPhone && !selectedPhoneOwner) {
                const ownerEdge = (graphEdges || []).find(e =>
                  (e.type === 'OWNS' || e.type === 'USES' || e.type === 'HAS_PHONE') &&
                  (e.target === selectedNode.id || e.source === selectedNode.id)
                );
                if (ownerEdge) {
                  const pId = ownerEdge.target === selectedNode.id ? ownerEdge.source : ownerEdge.target;
                  const pNode = (graphNodes || []).find(x => x.id === pId);
                  if (pNode && pNode.labels?.includes('Person')) {
                    selectedPhoneOwner = (pNode.properties?.name || pNode.name || pId) as string;
                    selectedPhoneOwnerId = pId;
                  }
                }
              }

              if (!isSelectedPhone || !selectedPhoneOwner || String(selectedPhoneOwner).toLowerCase() === 'unknown') return null;

              const cleanOwner = String(selectedPhoneOwner).split('\n')[0].replace(/^\(|\)$/g, '').trim();

              return (
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '12px 14px',
                    borderRadius: '8px',
                    background: 'rgba(59, 130, 246, 0.1)',
                    border: '1px solid rgba(59, 130, 246, 0.25)',
                    marginBottom: '16px',
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
                        {cleanOwner}
                      </div>
                      {selectedPhoneOwnerId && (
                        <div className="mono" style={{ fontSize: '11px', color: 'var(--text-dim)' }}>
                          Person ID: {selectedPhoneOwnerId}
                        </div>
                      )}
                    </div>
                  </div>
                  {selectedPhoneOwnerId && (
                    <button
                      className="neu-btn primary transition"
                      style={{ fontSize: '12px', padding: '5px 12px' }}
                      onClick={() => {
                        const pNode = graphNodes.find(n => n.id === selectedPhoneOwnerId);
                        if (pNode) {
                          setSelectedNode(pNode);
                        } else {
                          openEntityModal(selectedPhoneOwnerId);
                        }
                      }}
                    >
                      Inspect Person ➔
                    </button>
                  )}
                </div>
              );
            })()}

            <div className="flex items-center gap-3 mb-4" style={{display:'flex', alignItems:'center', gap:'12px', marginBottom:'16px'}}>
              <span className="dot" style={{width:'14px', height:'14px', background: (selectedNode.labels?.[0] && LABEL_COLOR[selectedNode.labels[0]]) || '#94a3b8', borderRadius:'50%'}}></span>
              <div>
                <div style={{fontWeight:700, fontSize:'16px'}}>{esc(selectedNode.name)}</div>
                <div className="mono" style={{color:'var(--text-faint)', fontSize:'12px'}}>{esc(selectedNode.id)}</div>
              </div>
              <span style={{marginLeft:'auto'}} className="tag plain">{selectedNode.labels?.join(', ')}</span>
            </div>
            <EntityPropertiesTable properties={selectedNode.properties || {}} labels={selectedNode.labels} />

            {/* Call & Communication Breakdown */}
            {Boolean(selectedNode.properties?.communications && Object.keys(selectedNode.properties.communications).length > 0) && (
              <div style={{ marginTop: '16px', padding: '14px 16px', borderRadius: '10px', background: 'var(--surface-hover)', border: '1px solid var(--border)' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px', flexWrap: 'wrap', gap: '8px' }}>
                  <div style={{ fontWeight: 700, fontSize: '13.5px', display: 'flex', alignItems: 'center', gap: '7px', color: 'var(--accent)' }}>
                    <span>📞</span> Call & Communication Frequency Breakdown
                  </div>
                  {selectedNode.properties?.total_calls !== undefined && (
                    <span className="tag plain" style={{ fontWeight: 700, fontSize: '11.5px', color: 'var(--accent)', border: '1px solid var(--accent)' }}>
                      Total Calls: {String(selectedNode.properties.total_calls)}
                    </span>
                  )}
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '220px', overflowY: 'auto' }}>
                  {Object.values((selectedNode.properties?.communications || {}) as Record<string, any>).map((c: any, cIdx: number) => {
                    const partnerId = c.partner_id;
                    const partnerName = c.partner_name || partnerId;
                    const callCount = c.call_count || 1;
                    return (
                      <div
                        key={cIdx}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          padding: '8px 12px',
                          borderRadius: '8px',
                          background: 'var(--card-bg)',
                          border: '1px solid var(--border)'
                        }}
                      >
                        <div>
                          <div style={{ fontWeight: 600, fontSize: '13px', color: 'var(--text)' }}>
                            {partnerName}
                          </div>
                          <div className="mono" style={{ fontSize: '11px', color: 'var(--text-dim)', marginTop: '2px' }}>
                            ID: {partnerId}
                          </div>
                        </div>
                        <div style={{ textAlign: 'right', display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '3px' }}>
                          <span
                            style={{
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '4px',
                              padding: '3px 10px',
                              borderRadius: '12px',
                              background: 'rgba(0, 210, 255, 0.15)',
                              color: 'var(--accent)',
                              fontWeight: 700,
                              fontSize: '12px',
                              border: '1px solid rgba(0, 210, 255, 0.3)'
                            }}
                          >
                            📞 {callCount} {callCount === 1 ? 'call' : 'calls'}
                          </span>
                          {c.summary && (
                            <span style={{ fontSize: '11px', color: 'var(--text-dim)' }}>
                              {c.summary}
                            </span>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Financial Transaction Breakdown */}
            {Boolean(selectedNode.properties?.transactions && Object.keys(selectedNode.properties.transactions).length > 0) && (
              <div style={{ marginTop: '16px', padding: '14px 16px', borderRadius: '10px', background: 'var(--surface-hover)', border: '1px solid var(--border)' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px', flexWrap: 'wrap', gap: '8px' }}>
                  <div style={{ fontWeight: 700, fontSize: '13.5px', display: 'flex', alignItems: 'center', gap: '7px', color: '#10b981' }}>
                    <span>💳</span> Financial Transactions & Fund Flow Breakdown
                  </div>
                  {selectedNode.properties?.total_transactions !== undefined && (
                    <span className="tag plain" style={{ fontWeight: 700, fontSize: '11.5px', color: '#10b981', border: '1px solid #10b981' }}>
                      Total Txns: {String(selectedNode.properties.total_transactions)}
                      {selectedNode.properties?.total_amount_transferred !== undefined ? ` (₹${Math.round(Number(selectedNode.properties.total_amount_transferred)).toLocaleString()})` : ''}
                    </span>
                  )}
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '220px', overflowY: 'auto' }}>
                  {Object.values((selectedNode.properties?.transactions || {}) as Record<string, any>).map((t: any, tIdx: number) => {
                    const partnerId = t.partner_id;
                    const partnerName = t.partner_name || partnerId;
                    const txCount = t.tx_count || 1;
                    return (
                      <div
                        key={tIdx}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          padding: '8px 12px',
                          borderRadius: '8px',
                          background: 'var(--card-bg)',
                          border: '1px solid var(--border)'
                        }}
                      >
                        <div>
                          <div style={{ fontWeight: 600, fontSize: '13px', color: 'var(--text)' }}>
                            {partnerName}
                          </div>
                          <div className="mono" style={{ fontSize: '11px', color: 'var(--text-dim)', marginTop: '2px' }}>
                            Account: {partnerId}
                          </div>
                        </div>
                        <div style={{ textAlign: 'right', display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '3px' }}>
                          <span
                            style={{
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '4px',
                              padding: '3px 10px',
                              borderRadius: '12px',
                              background: 'rgba(16, 185, 129, 0.15)',
                              color: '#10b981',
                              fontWeight: 700,
                              fontSize: '12px',
                              border: '1px solid rgba(16, 185, 129, 0.3)'
                            }}
                          >
                            💳 {txCount} {txCount === 1 ? 'txn' : 'txns'}
                          </span>
                          {t.summary ? (
                            <span style={{ fontSize: '11px', color: 'var(--text-dim)' }}>
                              {t.summary}
                            </span>
                          ) : t.total_amount ? (
                            <span style={{ fontSize: '11px', color: 'var(--text-dim)' }}>
                              ₹{Math.round(Number(t.total_amount)).toLocaleString()}
                            </span>
                          ) : null}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            <div className="flex gap-2.5 justify-end mt-4" style={{marginTop:'18px', display:'flex', gap:'10px', justifyContent:'flex-end'}}>
              <button className="neu-btn primary transition" onClick={() => openEntityModal(selectedNode.id)}>View Full Entity Profile</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
