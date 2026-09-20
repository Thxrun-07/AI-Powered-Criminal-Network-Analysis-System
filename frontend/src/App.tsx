import React, { useState, useEffect, useCallback } from 'react';
import {
  API,
  NAV,
  Case,
  Entity,
  Insight,
  HealthStatus,
  ViewId,
  ThemeMode,
  Toast,
  ModalState
} from './services/api';
import { Sidebar, Topbar } from './components/Sidebar';
import { OverviewModule } from './components/OverviewModule';
import { GraphExplorerModule } from './components/GraphExplorerModule';
import { EntitySearchModule } from './components/EntitySearchModule';
import { ShortestPathModule } from './components/ShortestPathModule';
import { RankingsModule } from './components/RankingsModule';
import { PatternInsightsModule } from './components/PatternInsightsModule';
import { BlockchainModule } from './components/BlockchainModule';
import { CaseRegistryModule } from './components/CaseRegistryModule';
import { DataIngestionModule } from './components/DataIngestionModule';
import {
  EntityModalContent,
  AiDossierModalContent,
  ResetDbConfirmContent,
  DeleteCaseConfirmContent
} from './components/Modals';

export default function App() {
  const [theme, setTheme] = useState<ThemeMode>(() => {
    const saved = localStorage.getItem('atlas_theme') as ThemeMode | null;
    if (saved === 'dark' || saved === 'light') return saved;
    return window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
  });
  const [view, setView] = useState<string>(() => {
    const h = location.hash.replace('#', '');
    return NAV.find(n => n.id === h) ? h : 'overview';
  });
  const [sidebarOpen, setSidebarOpen] = useState<boolean>(false);
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [cases, setCases] = useState<Case[]>([]);
  const [selectedCase, setSelectedCase] = useState<string | null>(null);
  const [insights, setInsights] = useState<Insight[]>([]);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [modal, setModal] = useState<ModalState | null>(null);

  // Apply theme to html root
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('atlas_theme', theme);
  }, [theme]);

  // Sync Hash
  useEffect(() => {
    const handleHashChange = () => {
      const h = location.hash.replace('#', '');
      if (NAV.find(n => n.id === h)) {
        setView(prev => (prev === h ? prev : h));
      }
    };
    window.addEventListener('hashchange', handleHashChange);
    return () => window.removeEventListener('hashchange', handleHashChange);
  }, []);

  const changeView = useCallback((newView: string): void => {
    setView(prev => {
      if (prev === newView) return prev;
      return newView;
    });
    setSidebarOpen(false);
    if (window.location.hash !== `#${newView}`) {
      window.history.replaceState(null, '', `#${newView}`);
    }
    window.scrollTo(0, 0);
  }, []);

  const addToast = useCallback((msg: string, type: string = 'info'): void => {
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
  const fetchHealth = useCallback(async (): Promise<void> => {
    try {
      const h = await API.get<HealthStatus>('/api/health');
      setHealth(h);
    } catch {
      setHealth(null);
    }
  }, []);

  // Load cases
  const fetchCases = useCallback(async (): Promise<Case[]> => {
    try {
      const list = await API.get<Case[]>('/api/cases?limit=200');
      setCases(list);
      return list;
    } catch (e: unknown) {
      const err = e as Error;
      addToast(`Failed to load cases: ${err.message}`, 'err');
      return [];
    }
  }, [addToast]);

  useEffect(() => {
    fetchHealth();
    fetchCases();
    const interval = setInterval(fetchHealth, 30000);
    return () => clearInterval(interval);
  }, [fetchHealth, fetchCases]);

  const toggleTheme = (): void => setTheme(prev => prev === 'dark' ? 'light' : 'dark');

  // Open Entity Modal
  const openEntityModal = useCallback(async (entityId: string): Promise<void> => {
    try {
      const e = await API.get<Record<string, unknown>>(`/api/entities/${encodeURIComponent(entityId)}`);
      setModal({ type: 'entity', data: e });
    } catch (err: unknown) {
      const error = err as Error;
      addToast(`Could not load entity: ${error.message}`, 'err');
    }
  }, [addToast]);

  // Open AI Insights Modal
  const openAiDossierModal = useCallback((caseId: string, caseName: string): void => {
    setModal({ type: 'ai_dossier', data: { caseId, caseName } });
  }, []);

  // Open Reset DB Confirmation
  const promptResetDatabase = useCallback((): void => {
    setModal({ type: 'reset_db' });
  }, []);

  // Open Delete Case Confirmation
  const promptDeleteCase = useCallback((caseId: string, caseName: string): void => {
    setModal({ type: 'delete_case', data: { caseId, caseName } });
  }, []);

  return (
    <React.Fragment>
      {/* Sidebar Mobile Overlay */}
      <div className={`overlay ${sidebarOpen ? 'open' : ''}`} onClick={() => setSidebarOpen(false)}></div>

      <div className="app relative z-[1]">
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
        <main className="main mx-auto">
          <Topbar
            view={view}
            health={health}
            theme={theme}
            toggleTheme={toggleTheme}
            setSidebarOpen={setSidebarOpen}
          />

          {/* View Component Dispatcher */}
          <div key={view} className="view-pane">
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
      <div id="toasts" className="fixed top-5 right-5 z-[9999] flex flex-col gap-2.5 pointer-events-none">
        {toasts.map(t => (
          <div key={t.id} className={`toast ${t.type} ${t.out ? 'out' : ''}`}>{t.msg}</div>
        ))}
      </div>

      {/* Global Modal Overlay */}
      {modal && (
        <div className="modal-overlay open" onClick={(e: React.MouseEvent<HTMLDivElement>) => { if (e.target === e.currentTarget) setModal(null); }}>
          <div className="modal">
            {modal.type === 'entity' && <EntityModalContent data={modal.data as unknown as Entity} onClose={() => setModal(null)} openEntityModal={openEntityModal} />}
            {modal.type === 'ai_dossier' && (
              <AiDossierModalContent
                caseId={String(modal.data?.caseId ?? '')}
                caseName={String(modal.data?.caseName ?? '')}
                onClose={() => setModal(null)}
              />
            )}
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
                caseId={String(modal.data?.caseId ?? '')}
                caseName={String(modal.data?.caseName ?? '')}
                onClose={() => setModal(null)}
                addToast={addToast}
                onSuccess={() => {
                  fetchCases();
                  if (selectedCase === modal.data?.caseId) setSelectedCase(null);
                }}
              />
            )}
          </div>
        </div>
      )}
    </React.Fragment>
  );
}
