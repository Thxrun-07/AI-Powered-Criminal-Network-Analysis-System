import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import * as vis from 'vis-network/standalone';
import { API, esc, LABEL_COLOR, getNodeLevel, getDeterministicSeed } from '../services/api.js';

export function GraphExplorerModule({ cases, selectedCase, setSelectedCase, openEntityModal, addToast, theme }) {
  const containerRef = useRef(null);
  const networkRef = useRef(null);
  const [caseFilter, setCaseFilter] = useState(selectedCase || '');
  const [layoutType, setLayoutType] = useState('structured');
  const [edgeLabelMode, setEdgeLabelMode] = useState('clean');
  const [limit, setLimit] = useState(1200);
  const [hideIsolated, setHideIsolated] = useState(false);
  const [physicsEnabled, setPhysicsEnabled] = useState(true);
  const [aiPanelCollapsed, setAiPanelCollapsed] = useState(false);
  const [graphNodes, setGraphNodes] = useState([]);
  const [graphEdges, setGraphEdges] = useState([]);
  const [selectedNode, setSelectedNode] = useState(null);
  const [loading, setLoading] = useState(false);

  // AI Copilot state
  const [aiChatLog, setAiChatLog] = useState([
    {
      sender: 'bot',
      model: 'Atlas Graph Assistant',
      content: "Can't get inferences from this visual topology? Ask me directly to identify key operatives, money flows, or hidden links.",
      chips: [
        '🎯 Who are the main targets?',
        '💸 Money laundering flow',
        '🔍 Summarize graph inference',
        '📱 Burner phone analysis'
      ]
    }
  ]);
  const [aiInput, setAiInput] = useState('');
  const [aiQuerying, setAiQuerying] = useState(false);

  const fetchGraph = useCallback(async () => {
    setLoading(true);
    try {
      const g = await API.get(`/api/graph?limit=${limit}${caseFilter ? `&case_id=${encodeURIComponent(caseFilter)}` : ''}`);
      setGraphNodes(g.nodes || []);
      setGraphEdges(g.edges || []);
    } catch (e) {
      addToast(`Failed to load graph: ${e.message}`, 'err');
    } finally {
      setLoading(false);
    }
  }, [limit, caseFilter, addToast]);

  useEffect(() => {
    fetchGraph();
  }, [fetchGraph]);

  // Render Network Graph
  useEffect(() => {
    if (!containerRef.current) return;
    if (networkRef.current) {
      networkRef.current.destroy();
      networkRef.current = null;
    }

    const isLight = theme === 'light';
    const textColor = isLight ? '#0f172a' : '#cbd5e1';
    const edgeColor = isLight ? 'rgba(51, 65, 85, 0.45)' : 'rgba(148, 163, 184, 0.4)';

    // Compute degrees
    const degrees = {};
    (graphEdges || []).forEach(e => {
      degrees[e.source] = (degrees[e.source] || 0) + 1;
      degrees[e.target] = (degrees[e.target] || 0) + 1;
    });

    const seenNodeIds = new Set();
    const nodes = [];
    (graphNodes || []).forEach(n => {
      if (!n || !n.id || seenNodeIds.has(n.id)) return;
      if (hideIsolated && (degrees[n.id] || 0) <= 1 && !n.labels?.includes('Case')) return;

      seenNodeIds.add(n.id);
      const isCase = n.labels?.includes('Case');
      const isPerson = n.labels?.includes('Person');

      nodes.push({
        id: n.id,
        label: n.name || n.id,
        level: getNodeLevel(n.labels),
        title: `${n.labels?.[0] || 'Node'}: ${n.name || n.id}\nID: ${n.id}`,
        shape: 'dot',
        size: isCase ? 22 : (isPerson ? 16 : 12),
        color: {
          background: LABEL_COLOR[n.labels?.[0]] || '#94a3b8',
          border: isLight ? '#ffffff' : '#070a12',
          highlight: { background: '#00d2ff', border: '#ffffff' }
        },
        font: {
          color: textColor,
          size: isCase ? 14 : (isPerson ? 12 : 10),
          face: 'Inter',
          strokeWidth: isLight ? 2 : 0,
          strokeColor: isLight ? '#ffffff' : 'transparent'
        }
      });
    });

    const seenEdgeIds = new Set();
    const edges = [];
    (graphEdges || []).forEach((e, idx) => {
      if (!e || !e.source || !e.target) return;
      if (!seenNodeIds.has(e.source) || !seenNodeIds.has(e.target)) return;

      let edgeId = String(e.id || `edge_${e.source}_${e.type}_${e.target}_${idx}`);
      if (seenEdgeIds.has(edgeId)) edgeId = `${edgeId}_${idx}`;
      seenEdgeIds.add(edgeId);

      const isCaseLink = e.type === 'INVOLVES';
      let label = e.type || '';
      if (edgeLabelMode === 'none') label = '';
      else if (edgeLabelMode === 'clean' && isCaseLink) label = '';

      edges.push({
        id: edgeId,
        from: e.source,
        to: e.target,
        label: label,
        title: `${e.type || 'LINK'} (${e.source} → ${e.target})`,
        arrows: 'to',
        color: {
          color: isCaseLink ? (isLight ? 'rgba(2, 132, 199, 0.35)' : 'rgba(0, 210, 255, 0.35)') : edgeColor,
          highlight: '#00d2ff', hover: '#00d2ff'
        },
        dashes: isCaseLink,
        font: {
          color: isLight ? '#475569' : '#94a3b8',
          size: 9, face: 'Inter', strokeWidth: 0,
          background: isLight ? 'rgba(255,255,255,0.85)' : 'rgba(12, 17, 30, 0.85)'
        },
        smooth: { enabled: true, type: 'continuous', roundness: 0.35 }
      });
    });

    const seed = getDeterministicSeed(caseFilter || 'all');
    let layoutOpts = { randomSeed: seed };
    let physicsOpts = {};

    if (layoutType === 'hierarchy_ud') {
      layoutOpts.hierarchical = { enabled: true, direction: 'UD', sortMethod: 'directed', levelSeparation: 140, nodeSpacing: 160 };
      physicsOpts = { enabled: physicsEnabled, solver: 'hierarchicalRepulsion', hierarchicalRepulsion: { nodeDistance: 150, centralGravity: 0.0, springLength: 120, springConstant: 0.04, damping: 0.48 } };
    } else if (layoutType === 'hierarchy_lr') {
      layoutOpts.hierarchical = { enabled: true, direction: 'LR', sortMethod: 'directed', levelSeparation: 170, nodeSpacing: 140 };
      physicsOpts = { enabled: physicsEnabled, solver: 'hierarchicalRepulsion', hierarchicalRepulsion: { nodeDistance: 140, centralGravity: 0.0, springLength: 120, springConstant: 0.04, damping: 0.48 } };
    } else if (layoutType === 'radial') {
      layoutOpts.improvedLayout = true;
      physicsOpts = { enabled: physicsEnabled, solver: 'forceAtlas2Based', forceAtlas2Based: { gravitationalConstant: -70, centralGravity: 0.04, springLength: 150, springConstant: 0.08, damping: 0.55, avoidOverlap: 0.85 } };
    } else {
      layoutOpts.improvedLayout = true;
      physicsOpts = { enabled: physicsEnabled, solver: 'forceAtlas2Based', forceAtlas2Based: { gravitationalConstant: -55, centralGravity: 0.015, springLength: 160, springConstant: 0.07, damping: 0.52, avoidOverlap: 0.90 } };
    }

    const net = new vis.Network(containerRef.current, { nodes, edges }, {
      layout: layoutOpts, physics: physicsOpts, nodes: { borderWidth: 2 }, edges: { width: 1.4 },
      interaction: { hover: true, tooltipDelay: 100, navigationButtons: true, keyboard: true }
    });

    net.on('click', p => {
      if (p.nodes && p.nodes.length) {
        const targetId = p.nodes[0];
        const nObj = graphNodes.find(n => n.id === targetId);
        if (nObj) setSelectedNode(nObj);
      }
    });

    networkRef.current = net;
  }, [graphNodes, graphEdges, layoutType, edgeLabelMode, hideIsolated, physicsEnabled, theme, caseFilter]);

  const handleAiQuerySubmit = async (e, promptOverride = null) => {
    if (e && e.preventDefault) e.preventDefault();
    const q = promptOverride || aiInput.trim();
    if (!q) return;

    if (!promptOverride) setAiInput('');
    setAiChatLog(prev => [...prev, { sender: 'user', content: q }]);
    setAiQuerying(true);

    try {
      const res = await API.post('/api/graph/ai-query', {
        question: q,
        case_id: caseFilter || null,
        nodes_count: graphNodes?.length || null,
        edges_count: graphEdges?.length || null,
        selected_node_id: selectedNode?.id || null
      });
      setAiChatLog(prev => [...prev, {
        sender: 'bot',
        model: res.ai_model || 'AI Copilot',
        content: res.answer || 'No specific inference generated.'
      }]);
    } catch (err) {
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
    const counts = {};
    (graphNodes || []).forEach(n => {
      const l = n.labels?.[0] || 'Entity';
      counts[l] = (counts[l] || 0) + 1;
    });
    return counts;
  }, [graphNodes]);

  return (
    <div>
      <div className="card">
        <div className="card-header">
          <div className="card-title">
            <svg viewBox="0 0 24 24" fill="none" strokeWidth="2" strokeLinecap="round"><path d="M12 3a2 2 0 0 1 2 2c0 .4-.1.8-.3 1.1l3.4 5.4c.3-.1.6-.2.9-.2a2 2 0 1 1 0 4c-.3 0-.6-.1-.9-.2l-3.4 5.4c.2.3.3.7.3 1.1a2 2 0 1 1-3.6-1.1L8.9 15.5c-.3.1-.6.2-.9.2a2 2 0 1 1 0-4c.3 0 .6.1.8.2l3.4-5.4c-.2-.3-.3-.7-.3-1.1a2 2 0 0 1 2-2Z"/></svg>
            Network Topology Explorer
          </div>
          <div className="row" style={{gap:'10px', alignItems:'flex-end', flexWrap:'wrap'}}>
            <div className="field" style={{minWidth:'180px'}}>
              <label>Case Filter</label>
              <select className="control" value={caseFilter} onChange={e => { setCaseFilter(e.target.value); setSelectedCase(e.target.value); }}>
                <option value="">All Ingested Cases</option>
                {cases.map(c => <option key={c.case_id} value={c.case_id}>{esc(c.case_name || c.case_id)}</option>)}
              </select>
            </div>
            <div className="field" style={{minWidth:'180px'}}>
              <label>Layout Structure</label>
              <select className="control" value={layoutType} onChange={e => setLayoutType(e.target.value)}>
                <option value="structured">🌟 Structured Organic (Reduced Bounce)</option>
                <option value="hierarchy_ud">🌳 Hierarchical Flow (Top-to-Bottom)</option>
                <option value="hierarchy_lr">🏛️ Pipeline Flow (Left-to-Right)</option>
                <option value="radial">🎯 Central Core & Radial Orbit</option>
              </select>
            </div>
            <div className="field" style={{maxWidth:'130px'}}>
              <label>Edge Labels</label>
              <select className="control" value={edgeLabelMode} onChange={e => setEdgeLabelMode(e.target.value)}>
                <option value="clean">Clean (Hide INVOLVES)</option>
                <option value="all">Show All</option>
                <option value="none">No Edge Text</option>
              </select>
            </div>
            <div className="field" style={{maxWidth:'110px'}}>
              <label>Limit</label>
              <select className="control" value={limit} onChange={e => setLimit(Number(e.target.value))}>
                <option value="300">300</option>
                <option value="600">600</option>
                <option value="1200">1200</option>
                <option value="2500">2500</option>
              </select>
            </div>
            <div style={{display:'flex', gap:'8px', alignItems:'flex-end'}}>
              <button className="neu-btn primary" disabled={loading} onClick={fetchGraph}>{loading ? 'Rendering…' : 'Render'}</button>
              <button className="neu-btn ghost" onClick={() => setAiPanelCollapsed(prev => !prev)} style={{display:'inline-flex', alignItems:'center', gap:'6px', color:'var(--accent)'}}>
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="m12 3-1.9 5.8a2 2 0 0 1-1.3 1.3L3 12l5.8 1.9a2 2 0 0 1 1.3 1.3L12 21l1.9-5.8a2 2 0 0 1 1.3-1.3L21 12l-5.8-1.9a2 2 0 0 1-1.3-1.3Z"/></svg>
                <span>{aiPanelCollapsed ? 'Show Copilot' : 'AI Copilot'}</span>
              </button>
              <button className="neu-btn ghost" onClick={() => { setPhysicsEnabled(p => !p); addToast(physicsEnabled ? 'Physics locked into place' : 'Physics simulation resumed', 'info'); }}>
                <span>{physicsEnabled ? '⏸ Pause' : '▶ Live Bounce'}</span>
              </button>
              <button className="neu-btn ghost" onClick={() => { if (networkRef.current) networkRef.current.fit({animation:{duration:600}}); }}>Fit</button>
            </div>
          </div>
        </div>

        <div style={{display:'flex', alignItems:'center', justifyContent:'space-between', gap:'14px', marginBottom:'12px', flexWrap:'wrap'}}>
          <label style={{display:'inline-flex', alignItems:'center', gap:'7px', fontSize:'12.5px', color:'var(--text-dim)', cursor:'pointer'}}>
            <input type="checkbox" checked={hideIsolated} onChange={e => setHideIsolated(e.target.checked)} style={{cursor:'pointer'}} />
            Hide Isolated 1-Hop Pairs (Focus Connected Core)
          </label>
          <div style={{fontSize:'12px', color:'var(--text-faint)'}}>
            Drag nodes to inspect · Click any node or ask the AI Copilot on the right for inferences
          </div>
        </div>

        <div id="graph">
          {loading && (
            <div style={{position:'absolute', inset:0, display:'flex', flexDirection:'column', alignItems:'center', justifyContent:'center', gap:'14px', color:'var(--text-dim)', background:'var(--graph-bg)', zIndex:10}}>
              <div className="status-dot" style={{width:'14px', height:'14px', background:'var(--accent)', animation:'pulse 1s infinite'}}></div>
              <div style={{fontSize:'13px'}}>Generating graph layout…</div>
            </div>
          )}
          <div id="graphCanvas" ref={containerRef}></div>

          {/* AI Copilot Side Structure */}
          <div className={`graph-ai-box ${aiPanelCollapsed ? 'collapsed' : ''}`}>
            <div className="graph-ai-header">
              <div style={{display:'flex', alignItems:'center', gap:'7px'}}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth="2"><path d="m12 3-1.9 5.8a2 2 0 0 1-1.3 1.3L3 12l5.8 1.9a2 2 0 0 1 1.3 1.3L12 21l1.9-5.8a2 2 0 0 1 1.3-1.3L21 12l-5.8-1.9a2 2 0 0 1-1.3-1.3Z"/></svg>
                <span style={{fontWeight:700, fontSize:'13px', color:'var(--text)'}}>AI Copilot</span>
                <span className="tag open" style={{padding:'1px 6px', fontSize:'9.5px', textTransform:'uppercase'}}>AI Inference</span>
              </div>
              <button className="neu-btn ghost" style={{padding:'2px 7px', fontSize:'11px'}} onClick={() => setAiPanelCollapsed(true)}>✕</button>
            </div>

            <div className="graph-ai-body">
              {aiChatLog.map((msg, idx) => (
                <div key={idx} className={`ai-msg ${msg.sender === 'user' ? 'user' : 'bot'}`} style={msg.error ? {borderColor:'rgba(239, 68, 68, 0.4)'} : {}}>
                  <div className="ai-msg-hdr">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="m12 3-1.9 5.8a2 2 0 0 1-1.3 1.3L3 12l5.8 1.9a2 2 0 0 1 1.3 1.3L12 21l1.9-5.8a2 2 0 0 1 1.3-1.3L21 12l-5.8-1.9a2 2 0 0 1-1.3-1.3Z"/></svg>
                    <span>{msg.sender === 'user' ? 'Investigator Query' : (msg.model || 'AI Copilot')}</span>
                  </div>
                  <div>{msg.content}</div>
                  {msg.chips && (
                    <div className="ai-quick-chips">
                      {msg.chips.map((c, cIdx) => (
                        <button key={cIdx} type="button" className="ai-chip" onClick={() => handleAiQuerySubmit(null, c.replace(/^[^a-zA-Z0-9]+/, ''))}>
                          {c}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              ))}
              {aiQuerying && (
                <div className="ai-msg bot">
                  <div className="ai-msg-hdr">
                    <div className="status-dot" style={{width:'8px', height:'8px', background:'var(--accent)', animation:'pulse 1s infinite'}}></div>
                    <span>AI is analyzing topology…</span>
                  </div>
                  <div style={{fontSize:'11.5px', color:'var(--text-faint)'}}>Correlating nodes, transactions, and hidden links</div>
                </div>
              )}
            </div>

            <div className="graph-ai-footer">
              <form onSubmit={handleAiQuerySubmit} style={{display:'flex', gap:'6px', width:'100%', margin:0}}>
                <input type="text" className="control" style={{fontSize:'12px', padding:'7px 10px', flex:1}} placeholder="Ask about this network…" value={aiInput} onChange={e => setAiInput(e.target.value)} />
                <button type="submit" className="neu-btn primary" disabled={aiQuerying} style={{padding:'0 12px', fontSize:'12px'}}>{aiQuerying ? '…' : 'Ask'}</button>
              </form>
            </div>
          </div>
        </div>

        <div className="legend">
          {Object.entries(nodeCounts).map(([k, v]) => (
            <div key={k} className="lg">
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
          <div className="card-header">
            <div className="card-title">Entity Inspection</div>
            <button className="neu-btn ghost" onClick={() => setSelectedNode(null)}>Close</button>
          </div>
          <div>
            <div style={{display:'flex', alignItems:'center', gap:'12px', marginBottom:'16px'}}>
              <span className="dot" style={{width:'14px', height:'14px', background: LABEL_COLOR[selectedNode.labels?.[0]] || '#94a3b8', borderRadius:'50%'}}></span>
              <div>
                <div style={{fontWeight:700, fontSize:'16px'}}>{esc(selectedNode.name)}</div>
                <div className="mono" style={{color:'var(--text-faint)', fontSize:'12px'}}>{esc(selectedNode.id)}</div>
              </div>
              <span style={{marginLeft:'auto'}} className="tag plain">{selectedNode.labels?.join(', ')}</span>
            </div>
            <div className="kv">
              {Object.entries(selectedNode.properties || {})
                .filter(([k]) => !['case_ids', 'created_at', 'updated_at'].includes(k))
                .slice(0, 12)
                .map(([k, v]) => (
                  <div key={k}>
                    <div className="k">{esc(k)}</div>
                    <div className="v mono">{esc(typeof v === 'object' ? JSON.stringify(v) : v)}</div>
                  </div>
                ))}
            </div>
            <div style={{marginTop:'18px', display:'flex', gap:'10px', justifyContent:'flex-end'}}>
              <button className="neu-btn primary" onClick={() => openEntityModal(selectedNode.id)}>View Full Entity Profile</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
