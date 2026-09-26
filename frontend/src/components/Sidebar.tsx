import React, { useState, useEffect, useRef } from 'react';
import { NAV, TITLES, HealthStatus, OfficerSession } from '../services/api';

export interface HeaderNavProps {
  view: string;
  changeView: (id: string) => void;
  theme?: string;
  toggleTheme?: () => void;
  health: HealthStatus | null;
  officerSession: OfficerSession | null;
  promptResetDatabase?: () => void;
}

// Workflow category groupings for Dashboard with expandable sub-features
export const WORKFLOW_CATEGORIES = [
  {
    id: 'overview',
    label: 'Command Center',
    icon: 'M4 13 9 4l5 9H4Zm6 0 5-8 5 8h-10Z',
    views: ['overview']
  },
  {
    id: 'network',
    label: 'Network Studio',
    icon: 'M12 3a2 2 0 0 1 2 2c0 .4-.1.8-.3 1.1l3.4 5.4c.3-.1.6-.2.9-.2a2 2 0 1 1 0 4c-.3 0-.6-.1-.9-.2l-3.4 5.4c.2.3.3.7.3 1.1a2 2 0 1 1-3.6-1.1L8.9 15.5c-.3.1-.6.2-.9.2a2 2 0 1 1 0-4c.3 0 .6.1.8.2l3.4-5.4c-.2-.3-.3-.7-.3-1.1a2 2 0 0 1 2-2Z',
    views: ['graph', 'path']
  },
  {
    id: 'intel',
    label: 'Intelligence Hub',
    icon: 'M11 19a8 8 0 1 0 0-16 8 8 0 0 0 0 16Zm10 2-4.35-4.35',
    views: ['search', 'rankings', 'insights']
  },
  {
    id: 'evidence',
    label: 'Evidence & Cases',
    icon: 'M3 7a2 2 0 0 1 2-2h5l2 2h9a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7Z',
    views: ['cases', 'blockchain']
  }
];

export function TopHeader({
  health,
  officerSession,
  setOfficerSession,
  changeView,
  addToast
}: {
  health: HealthStatus | null;
  officerSession: OfficerSession | null;
  setOfficerSession?: React.Dispatch<React.SetStateAction<OfficerSession | null>>;
  changeView: (id: string) => void;
  addToast?: (msg: string, type?: string) => void;
}) {
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Close dropdown on click outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setDropdownOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleLogout = () => {
    setDropdownOpen(false);
    if (setOfficerSession) {
      setOfficerSession(null);
    }
    localStorage.removeItem('atlas_officer_session');
    if (addToast) {
      addToast('Signed out of ATLAS session successfully', 'info');
    }
    changeView('home');
  };

  const officerName = officerSession?.officerName || 'Guest Officer';
  const badgeId = officerSession?.badgeNumber || 'UNASSIGNED';
  const clearance = officerSession?.clearanceLevel ? officerSession.clearanceLevel.split(':')[0] : 'UNVERIFIED';

  return (
    <header className="app-top-header">
      {/* Left: Brand */}
      <div
        className="top-brand cursor-pointer"
        onClick={() => changeView('home')}
        title="ATLAS - Return to Landing Page"
      >
        <svg viewBox="0 0 24 24" width="22" height="22" fill="currentColor">
          <path d="M4 9a1.5 1.5 0 0 1 3 0v6a1.5 1.5 0 0 1-2 0V9zm5-4a1.5 1.5 0 0 1 3 0v14a1.5 1.5 0 0 1-3 0V5zm5 3a1.5 1.5 0 0 1 3 0v8a1.5 1.5 0 0 1-3 0V8zm5 3a1.5 1.5 0 0 1 3 0v2a1.5 1.5 0 0 1-3 0v-2z" />
        </svg>
        <div className="flex items-center gap-2">
          <span className="top-brand-title">ATLAS</span>
          <span className="top-brand-subtitle">CRIMINAL NETWORK ANALYSIS SYSTEM</span>
        </div>
      </div>

      {/* Right: DB status + User with Dropdown */}
      <div className="top-right-actions">
        {/* Database Health Pill */}
        <div className="status-pill">
          <span className={`status-dot ${health ? 'ok' : 'bad'}`}></span>
          <span>{health ? 'Database Active' : 'Connecting…'}</span>
          {health && health.latency_ms != null && (
            <span className="status-meta">{Math.round(health.latency_ms)}ms</span>
          )}
        </div>

        {/* User with Dropdown as Logout / Login */}
        <div className="user-dropdown-container" ref={dropdownRef}>
          <button
            type="button"
            className="user-dropdown-btn"
            onClick={() => setDropdownOpen(prev => !prev)}
            aria-expanded={dropdownOpen}
            title="User Profile & Session Settings"
          >
            {/* User Shield Icon */}
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ color: 'var(--text)' }}>
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
            </svg>
            <span className="user-display-name">{officerName}</span>
            <span className={`tag ${officerSession ? 'open' : ''}`} style={{ padding: '1px 6px', fontSize: '9.5px' }}>
              {clearance}
            </span>
            <svg
              className={`user-chevron ${dropdownOpen ? 'open' : ''}`}
              viewBox="0 0 24 24"
              width="13"
              height="13"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <polyline points="6 9 12 15 18 9" />
            </svg>
          </button>

          {dropdownOpen && (
            <div className="user-dropdown-menu">
              <div className="dropdown-user-info">
                <div className="dropdown-officer-name">{officerName}</div>
                <div className="dropdown-officer-meta">Badge: {badgeId}</div>
                <div className="dropdown-officer-meta">{officerSession?.clearanceLevel || 'Unauthenticated Session'}</div>
                <div className="dropdown-officer-dept">{officerSession?.department || 'Guest Access'}</div>
              </div>

              <div className="dropdown-divider"></div>

              <button
                type="button"
                className="dropdown-item"
                onClick={() => {
                  setDropdownOpen(false);
                  changeView('home');
                }}
              >
                <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
                  <polyline points="9 22 9 12 15 12 15 22" />
                </svg>
                <span>Return to Landing Page</span>
              </button>

              {officerSession ? (
                <button
                  type="button"
                  className="dropdown-item logout"
                  onClick={handleLogout}
                >
                  <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
                    <polyline points="16 17 21 12 16 7" />
                    <line x1="21" y1="12" x2="9" y2="12" />
                  </svg>
                  <span>Logout</span>
                </button>
              ) : (
                <button
                  type="button"
                  className="dropdown-item logout"
                  onClick={() => {
                    setDropdownOpen(false);
                    changeView('auth');
                  }}
                >
                  <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4" />
                    <polyline points="10 17 15 12 10 7" />
                    <line x1="15" y1="12" x2="3" y2="12" />
                  </svg>
                  <span>Sign In / Sign Up</span>
                </button>
              )}
            </div>
          )}
        </div>

      </div>
    </header>
  );
}

export function Sidebar({
  view,
  changeView
}: {
  view: string;
  changeView: (id: string) => void;
  theme?: string;
  toggleTheme?: () => void;
  sidebarOpen?: boolean;
  setSidebarOpen?: (open: boolean | ((prev: boolean) => boolean)) => void;
  promptResetDatabase?: () => void;
}) {
  // State tracking which categories are expanded in accordion
  const [expandedCategories, setExpandedCategories] = useState<Record<string, boolean>>(() => {
    const initial: Record<string, boolean> = {
      network: false,
      intel: false,
      evidence: false
    };
    const activeCat = WORKFLOW_CATEGORIES.find(cat => cat.views.includes(view));
    if (activeCat && activeCat.id !== 'overview') {
      initial[activeCat.id] = true;
    } else {
      initial.network = true;
    }
    return initial;
  });

  // Auto-expand category when view changes
  useEffect(() => {
    const activeCat = WORKFLOW_CATEGORIES.find(cat => cat.views.includes(view));
    if (activeCat && activeCat.id !== 'overview') {
      setExpandedCategories(prev => ({
        ...prev,
        [activeCat.id]: true
      }));
    }
  }, [view]);

  const handleCategoryClick = (cat: typeof WORKFLOW_CATEGORIES[0]) => {
    if (cat.views.length === 1) {
      changeView(cat.views[0]);
      return;
    }

    const isCurrentlyExpanded = !!expandedCategories[cat.id];
    const isInsideCurrentCategory = cat.views.includes(view);

    if (!isCurrentlyExpanded) {
      setExpandedCategories(prev => ({ ...prev, [cat.id]: true }));
      if (!isInsideCurrentCategory) {
        changeView(cat.views[0]);
      }
    } else {
      if (isInsideCurrentCategory) {
        setExpandedCategories(prev => ({ ...prev, [cat.id]: false }));
      } else {
        changeView(cat.views[0]);
      }
    }
  };

  return (
    <aside className="app-sidebar">
      {/* Navigation Accordion Sections */}
      <nav className="sidebar-nav-container">
        <div className="sidebar-section-title">MAIN NAVIGATION</div>

        <div className="sidebar-nav-list">
          {WORKFLOW_CATEGORIES.map(cat => {
            const isCategoryActive = cat.views.includes(view);
            const isSingleView = cat.views.length === 1;
            const isExpanded = !isSingleView && !!expandedCategories[cat.id];

            if (isSingleView) {
              return (
                <div key={cat.id} className="sidebar-nav-group">
                  <button
                    type="button"
                    className={`sidebar-category-btn ${isCategoryActive ? 'active' : ''}`}
                    onClick={() => handleCategoryClick(cat)}
                  >
                    <div className="flex items-center gap-2.5">
                      <svg viewBox="0 0 24 24" fill="none" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="nav-cat-icon">
                        <path d={cat.icon} />
                      </svg>
                      <span className="nav-cat-label">{cat.label}</span>
                    </div>
                  </button>
                </div>
              );
            }

            return (
              <div key={cat.id} className={`sidebar-nav-group ${isExpanded ? 'expanded' : ''}`}>
                {/* Category Header Button */}
                <button
                  type="button"
                  className={`sidebar-category-btn ${isCategoryActive ? 'in-category' : ''}`}
                  onClick={() => handleCategoryClick(cat)}
                  aria-expanded={isExpanded}
                >
                  <div className="flex items-center gap-2.5">
                    <svg viewBox="0 0 24 24" fill="none" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="nav-cat-icon">
                      <path d={cat.icon} />
                    </svg>
                    <span className="nav-cat-label">{cat.label}</span>
                  </div>
                  <svg
                    className={`accordion-chevron ${isExpanded ? 'open' : ''}`}
                    viewBox="0 0 24 24"
                    width="13"
                    height="13"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <polyline points="6 9 12 15 18 9" />
                  </svg>
                </button>

                {/* Sub-items accordion dropdown */}
                {isExpanded && (
                  <div className="sidebar-sub-menu">
                    {cat.views.map(vId => {
                      const navItem = NAV.find(n => n.id === vId);
                      if (!navItem) return null;
                      const isSubActive = view === vId;

                      return (
                        <button
                          key={vId}
                          type="button"
                          className={`sidebar-sub-item ${isSubActive ? 'active' : ''}`}
                          onClick={() => changeView(vId)}
                        >
                          <svg viewBox="0 0 24 24" fill="none" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="sub-item-icon">
                            <path d={navItem.icon} />
                          </svg>
                          <span>{navItem.label}</span>
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </nav>
    </aside>
  );
}

// Backward compatibility export if needed
export function Topbar({
  view
}: {
  view: string;
  health?: HealthStatus | null;
  theme?: string;
  toggleTheme?: () => void;
  officerSession?: OfficerSession | null;
  changeView?: (id: string) => void;
  setSidebarOpen?: (open: boolean | ((prev: boolean) => boolean)) => void;
}) {
  return (
    <div className="view-banner">
      <h1>{TITLES[view]?.[0] || 'Command Center'}</h1>
      <p>{TITLES[view]?.[1] || 'Criminal Network Topology & Link Intelligence'}</p>
    </div>
  );
}
