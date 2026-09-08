import React, { useState, useEffect, useCallback } from 'react';
import { API, NAV } from './services/api.js';
import { Sidebar, Topbar } from './components/Sidebar.jsx';
import { OverviewModule } from './components/OverviewModule.jsx';
import { GraphExplorerModule } from './components/GraphExplorerModule.jsx';
import { EntitySearchModule } from './components/EntitySearchModule.jsx';
import { ShortestPathModule } from './components/ShortestPathModule.jsx';
import { RankingsModule } from './components/RankingsModule.jsx';
import { PatternInsightsModule } from './components/PatternInsightsModule.jsx';
import { BlockchainModule } from './components/BlockchainModule.jsx';
import { CaseRegistryModule } from './components/CaseRegistryModule.jsx';
import { DataIngestionModule } from './components/DataIngestionModule.jsx';
import { EntityModalContent, AiDossierModalContent, ResetDbConfirmContent, DeleteCaseConfirmContent } from './components/Modals.jsx';

export default function App() {
  const [theme, setTheme] = useState(() => {
    const saved = localStorage.getItem('atlas_theme');
    if (saved) return saved;
    return window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
  });
  const [view, setView] = useState(() => {
    const h = location.hash.replace('#', '');
    return NAV.find(n => n.id === h) ? h : 'overview';
  });
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [health, setHealth] = useState(null);
  const [cases, setCases] = useState([]);
  const [selectedCase, setSelectedCase] = useState(null);
  const [insights, setInsights] = useState([]);
  const [toasts, setToasts] = useState([]);
  const [modal, setModal] = useState(null);

  // Apply theme to html root
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('atlas_theme', theme);
  }, [theme]);

  // Sync Hash
  useEffect(() => {
    const handleHashChange = () => {
      const h = location.hash.replace('#', '');
      if (NAV.find(n => n.id === h)) setView(h);
    };
    window.addEventListener('hashchange', handleHashChange);
    return () => window.removeEventListener('hashchange', handleHashChange);
  }, []);

  const changeView = (newView) => {
    setView(newView);
    setSidebarOpen(false);
    location.hash = newView;
  };

  const addToast = useCallback((msg, type = 'info') => {
    const id = Date.now() + Math.random();
    setToasts(prev => [...prev, { id, msg, type, out: false }]);
    setTimeout(() => {
      setToasts(prev => prev.map(t => t.id === id ? { ...t, out: true } : t));
      setTimeout(() => {
        setToasts(prev => prev.filter(t => t.id !== id));
      }, 350);
    }, type === 'err' ? 6500 : 3800);
  }, []);

  // Health check
  const fetchHealth = useCallback(async () => {
    try {
      const h = await API.get('/api/health');
      setHealth(h);
    } catch (e) {
      setHealth(null);
    }
  }, []);

  // Load cases
  const fetchCases = useCallback(async () => {
    try {
      const list = await API.get('/api/cases?limit=200');
      setCases(list);
      return list;
    } catch (e) {
      addToast(`Failed to load cases: ${e.message}`, 'err');
      return [];
    }
  }, [addToast]);

  useEffect(() => {
    fetchHealth();
    fetchCases();
    const interval = setInterval(fetchHealth, 30000);
    return () => clearInterval(interval);
  }, [fetchHealth, fetchCases]);

  const toggleTheme = () => setTheme(prev => prev === 'dark' ? 'light' : 'dark');

  // Open Entity Modal
  const openEntityModal = useCallback(async (entityId) => {
    try {
      const e = await API.get(`/api/entities/${encodeURIComponent(entityId)}`);
      setModal({ type: 'entity', data: e });
    } catch (err) {
      addToast(`Could not load entity: ${err.message}`, 'err');
    }
  }, [addToast]);

  // Open AI Insights Modal
  const openAiDossierModal = useCallback((caseId, caseName) => {
    setModal({ type: 'ai_dossier', data: { caseId, caseName } });
  }, []);

  // Open Reset DB Confirmation
  const promptResetDatabase = useCallback(() => {
    setModal({ type: 'reset_db' });
  }, []);

  // Open Delete Case Confirmation
  const promptDeleteCase = useCallback((caseId, caseName) => {
    setModal({ type: 'delete_case', data: { caseId, caseName } });
  }, []);

  return (
    <React.Fragment>
      {/* Sidebar Mobile Overlay */}
      <div className={`overlay ${sidebarOpen ? 'open' : ''}`} onClick={() => setSidebarOpen(false)}></div>

      <div className="app">
        {/* Sidebar */}
        <Sidebar
          view={view}
          changeView={changeView}
          theme={theme}
          toggleTheme={toggleTheme}
          sidebarOpen={sidebarOpen}
          setSidebarOpen={setSidebarOpen}
          promptResetDatabase={promptResetDatabase}
        />

        {/* Main Content Area */}
        <main className="main">
          <Topbar
            view={view}
            health={health}
            theme={theme}
            toggleTheme={toggleTheme}
            setSidebarOpen={setSidebarOpen}
          />

          {/* View Component Dispatcher */}
          <div key={view} className="fade-in">
            {view === 'overview' && <OverviewModule cases={cases} health={health} insights={insights} setInsights={setInsights} changeView={changeView} openAiDossier={openAiDossierModal} />}
            {view === 'graph' && <GraphExplorerModule cases={cases} selectedCase={selectedCase} setSelectedCase={setSelectedCase} openEntityModal={openEntityModal} addToast={addToast} theme={theme} />}
            {view === 'search' && <EntitySearchModule openEntityModal={openEntityModal} addToast={addToast} />}
            {view === 'path' && <ShortestPathModule openEntityModal={openEntityModal} addToast={addToast} />}
            {view === 'rankings' && <RankingsModule cases={cases} openEntityModal={openEntityModal} addToast={addToast} />}
            {view === 'insights' && <PatternInsightsModule cases={cases} insights={insights} setInsights={setInsights} openAiDossier={openAiDossierModal} addToast={addToast} />}
            {view === 'blockchain' && <BlockchainModule cases={cases} fetchCases={fetchCases} addToast={addToast} />}
            {view === 'cases' && <CaseRegistryModule cases={cases} fetchCases={fetchCases} selectedCase={selectedCase} setSelectedCase={setSelectedCase} openAiDossier={openAiDossierModal} promptDeleteCase={promptDeleteCase} changeView={changeView} theme={theme} addToast={addToast} />}
            {view === 'ingest' && <DataIngestionModule fetchCases={fetchCases} changeView={changeView} addToast={addToast} />}
          </div>
        </main>
      </div>

      {/* Toast Notifications */}
      <div id="toasts">
        {toasts.map(t => (
          <div key={t.id} className={`toast ${t.type} ${t.out ? 'out' : ''}`}>{t.msg}</div>
        ))}
      </div>

      {/* Global Modal Overlay */}
      {modal && (
        <div className="modal-overlay open" onClick={(e) => { if (e.target === e.currentTarget) setModal(null); }}>
          <div className="modal">
            {modal.type === 'entity' && <EntityModalContent data={modal.data} onClose={() => setModal(null)} openEntityModal={openEntityModal} />}
            {modal.type === 'ai_dossier' && <AiDossierModalContent caseId={modal.data.caseId} caseName={modal.data.caseName} onClose={() => setModal(null)} />}
            {modal.type === 'reset_db' && (
              <ResetDbConfirmContent
                onClose={() => setModal(null)}
                addToast={addToast}
                onSuccess={() => {
                  fetchCases();
                  setInsights([]);
                  changeView('overview');
                }}
              />
            )}
            {modal.type === 'delete_case' && (
              <DeleteCaseConfirmContent
                caseId={modal.data.caseId}
                caseName={modal.data.caseName}
                onClose={() => setModal(null)}
                addToast={addToast}
                onSuccess={() => {
                  fetchCases();
                  if (selectedCase === modal.data.caseId) setSelectedCase(null);
                }}
              />
            )}
          </div>
        </div>
      )}
    </React.Fragment>
  );
}
