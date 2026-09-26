import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  API,
  NAV,
  TITLES,
  Case,
  Entity,
  Insight,
  HealthStatus,
  ViewId,
  ThemeMode,
  Toast,
  ModalState,
  OfficerSession,
  filterCasesForOfficer
} from './services/api';
import { Sidebar, TopHeader } from './components/Sidebar';
import { HomeModule } from './components/HomeModule';
import { AuthModule } from './components/AuthModule';
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
import { LocalCaseStore } from './services/fileStore';


export default function App() {
  // Default to clean Light Theme as requested
  const [theme, setTheme] = useState<ThemeMode>(() => {
    const saved = localStorage.getItem('atlas_theme') as ThemeMode | null;
    if (saved === 'dark' || saved === 'light') return saved;
    return 'light';
  });

  // Default to dedicated Home page
  const [view, setView] = useState<string>(() => {
    const h = location.hash.replace('#', '');
    return NAV.find(n => n.id === h) || h === 'auth' ? h : 'home';
  });

  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [cases, setCases] = useState<Case[]>([]);
  const [selectedCase, setSelectedCase] = useState<string | null>(null);
  const [insights, setInsights] = useState<Insight[]>([]);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [modal, setModal] = useState<ModalState | null>(null);

  // Dynamic Investigator Session (No hardcoded default officer)
  const [officerSession, setOfficerSession] = useState<OfficerSession | null>(() => {
    try {
      const saved = localStorage.getItem('atlas_officer_session');
      if (saved) {
        return JSON.parse(saved);
      }
      return null;
    } catch {
      return null;
    }
  });


  useEffect(() => {
    if (officerSession) {
      localStorage.setItem('atlas_officer_session', JSON.stringify(officerSession));
    } else {
      localStorage.removeItem('atlas_officer_session');
    }
  }, [officerSession]);

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
  // Load cases (merges API cases with local persistent uploaded cases)
  const fetchCases = useCallback(async (): Promise<Case[]> => {
    let apiCases: Case[] = [];
    try {
      apiCases = await API.get<Case[]>('/api/cases?limit=200');
    } catch {
      apiCases = [];
    }

    const localCases = LocalCaseStore.getAll();
    const mergedMap = new Map<string, Case>();

    // 1. Add API cases
    apiCases.forEach(c => {
      if (c && c.case_id) {
        mergedMap.set(c.case_id.toLowerCase(), c);
      }
    });

    // 2. Add / merge local uploaded cases
    localCases.forEach(c => {
      if (c && c.case_id) {
        const key = c.case_id.toLowerCase();
        if (mergedMap.has(key)) {
          mergedMap.set(key, { ...mergedMap.get(key), ...c });
        } else {
          mergedMap.set(key, c);
        }
      }
    });

    const list = Array.from(mergedMap.values());
    setCases(list);
    return list;
  }, []);


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

  // Filter cases visible to the active officer session
  const visibleCases = useMemo(() => {
    return filterCasesForOfficer(cases, officerSession);
  }, [cases, officerSession]);

  return (
    <React.Fragment>
      {/* Dedicated Dynamic Auth Page */}
      {view === 'auth' ? (
        <AuthModule
          setOfficerSession={setOfficerSession}
          changeView={changeView}
          addToast={addToast}
        />
      ) : view === 'home' ? (
        <HomeModule
          cases={visibleCases}
          health={health}
          insights={insights}
          officerSession={officerSession}
          setOfficerSession={setOfficerSession}
          changeView={changeView}
          setSelectedCase={setSelectedCase}
          addToast={addToast}
        />
      ) : (
        <div className="app-shell">
          {/* Top Bar: Left ATLAS brand, Right corner user profile with dropdown as logout */}
          <TopHeader
            health={health}
            officerSession={officerSession}
            setOfficerSession={setOfficerSession}
            changeView={changeView}
            addToast={addToast}
          />

          <div className="app-layout">
            {/* Left Vertical Navigation Bar with Expandable Tabs */}
            <Sidebar
              view={view}
              changeView={changeView}
            />

            {/* Main Right Content Area */}
            <div className="app-content">
              <div className="view-banner">
                <h1>{TITLES[view]?.[0] || 'Command Center'}</h1>
                <p>{TITLES[view]?.[1] || 'Criminal Network Topology & Link Intelligence'}</p>
              </div>

              <main className="main">
              {/* View Component Dispatcher */}
              <div key={view} className="view-pane">
                {view === 'overview' && (
                  <OverviewModule
                    cases={visibleCases}
                    health={health}
                    insights={insights}
                    setInsights={setInsights}
                    changeView={changeView}
                    openAiDossier={openAiDossierModal}
                  />
                )}
                {view === 'graph' && (
                  <GraphExplorerModule
                    cases={visibleCases}
                    selectedCase={selectedCase}
                    setSelectedCase={setSelectedCase}
                    openEntityModal={openEntityModal}
                    addToast={addToast}
                    theme={theme}
                  />
                )}
                {view === 'search' && (
                  <EntitySearchModule
                    openEntityModal={openEntityModal}
                    addToast={addToast}
                  />
                )}
                {view === 'path' && (
                  <ShortestPathModule
                    openEntityModal={openEntityModal}
                    addToast={addToast}
                  />
                )}
                {view === 'rankings' && (
                  <RankingsModule
                    cases={visibleCases}
                    openEntityModal={openEntityModal}
                    addToast={addToast}
                  />
                )}
                {view === 'insights' && (
                  <PatternInsightsModule
                    cases={visibleCases}
                    insights={insights}
                    setInsights={setInsights}
                    openAiDossier={openAiDossierModal}
                    addToast={addToast}
                  />
                )}
                {view === 'blockchain' && (
                  <BlockchainModule
                    cases={visibleCases}
                    fetchCases={fetchCases}
                    addToast={addToast}
                  />
                )}
                {view === 'cases' && (
                  <CaseRegistryModule
                    officerSession={officerSession}
                    cases={visibleCases}
                    fetchCases={fetchCases}
                    selectedCase={selectedCase}
                    setSelectedCase={setSelectedCase}
                    openAiDossier={openAiDossierModal}
                    promptDeleteCase={promptDeleteCase}
                    changeView={changeView}
                    theme={theme}
                    addToast={addToast}
                  />
                )}
                {view === 'ingest' && (
                  <DataIngestionModule
                    officerSession={officerSession}
                    fetchCases={fetchCases}
                    changeView={changeView}
                    addToast={addToast}
                  />
                )}
              </div>
            </main>
          </div>
        </div>
      </div>
    )}


      {/* Toast Notifications */}
      <div id="toasts">
        {toasts.map(t => (
          <div key={t.id} className={`toast ${t.type} ${t.out ? 'out' : ''}`}>{t.msg}</div>
        ))}
      </div>

      {/* Global Modal Overlay */}
      {modal && (
        <div
          className="modal-overlay open"
          onClick={(e: React.MouseEvent<HTMLDivElement>) => {
            if (e.target === e.currentTarget) setModal(null);
          }}
        >
          <div className="modal">
            {modal.type === 'entity' && (
              <EntityModalContent
                data={modal.data as unknown as Entity}
                onClose={() => setModal(null)}
                openEntityModal={openEntityModal}
              />
            )}
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
                  changeView('home');
                }}
              />
            )}
            {modal.type === 'delete_case' && (
              <DeleteCaseConfirmContent
                caseId={String(modal.data?.caseId ?? '')}
                caseName={String(modal.data?.caseName ?? '')}
                onClose={() => setModal(null)}
                addToast={addToast}
                officerBadge={officerSession?.badgeNumber}
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
