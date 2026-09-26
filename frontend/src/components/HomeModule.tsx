import React, { useState, useEffect } from 'react';
import { Case, HealthStatus, Insight, OfficerSession } from '../services/api';
import { AuthModule } from './AuthModule';

export interface HomeModuleProps {
  cases: Case[];
  health: HealthStatus | null;
  insights: Insight[];
  officerSession: OfficerSession | null;
  setOfficerSession: (session: OfficerSession | null) => void;
  changeView: (view: string) => void;
  setSelectedCase: (id: string | null) => void;
  addToast: (msg: string, type?: string) => void;
}

export function HomeModule({
  cases,
  health,
  insights,
  officerSession,
  setOfficerSession,
  changeView,
  setSelectedCase,
  addToast
}: HomeModuleProps) {
  const [isAuthModalOpen, setIsAuthModalOpen] = useState<boolean>(false);
  const [activeSection, setActiveSection] = useState<'hero' | 'features' | 'how'>('hero');

  // Track scroll position to highlight the active section in the nav bar
  useEffect(() => {
    const handleScroll = () => {
      const engineEl = document.getElementById('intelligence-engine');
      const dataEl = document.getElementById('data-to-directory');

      if (!engineEl || !dataEl) return;

      const engineRect = engineEl.getBoundingClientRect();
      const dataRect = dataEl.getBoundingClientRect();

      if (dataRect.top <= 260) {
        setActiveSection('how');
      } else if (engineRect.top <= 260) {
        setActiveSection('features');
      } else {
        setActiveSection('hero');
      }
    };

    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  // Intersection Observer for scroll-triggered floating reveal animation
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add('is-visible');
          }
        });
      },
      {
        threshold: 0.1,
        rootMargin: '0px 0px -40px 0px',
      }
    );

    const elements = document.querySelectorAll('.scroll-float');
    elements.forEach((el) => observer.observe(el));

    return () => observer.disconnect();
  }, []);

  const handleCtaClick = () => {
    if (officerSession) {
      changeView('overview');
    } else {
      setIsAuthModalOpen(true);
    }
  };

  const scrollToHero = () => {
    window.scrollTo({ top: 0, behavior: 'smooth' });
    setActiveSection('hero');
  };

  const scrollToFeatures = () => {
    const el = document.getElementById('intelligence-engine');
    if (el) {
      el.scrollIntoView({ behavior: 'smooth' });
      setActiveSection('features');
    }
  };

  const scrollToHow = () => {
    const el = document.getElementById('data-to-directory');
    if (el) {
      el.scrollIntoView({ behavior: 'smooth' });
      setActiveSection('how');
    }
  };

  return (
    <div className="landing-shell">
      {/* Top Sticky Navigation Bar */}
      <header className="landing-nav-wrapper">
        <div className="landing-nav">
          {/* Left: Waveform Icon + ATLAS */}
          <div
            className="landing-brand"
            onClick={scrollToHero}
            title="ATLAS Home"
          >
            <svg viewBox="0 0 24 24" width="22" height="22" fill="currentColor">
              <path d="M4 9a1.5 1.5 0 0 1 3 0v6a1.5 1.5 0 0 1-3 0V9zm5-4a1.5 1.5 0 0 1 3 0v14a1.5 1.5 0 0 1-3 0V5zm5 3a1.5 1.5 0 0 1 3 0v8a1.5 1.5 0 0 1-3 0V8zm5 3a1.5 1.5 0 0 1 3 0v2a1.5 1.5 0 0 1-3 0v-2z" />
            </svg>
            <span style={{ fontFamily: 'var(--font)', fontWeight: 800, letterSpacing: '-0.3px', fontSize: '20px' }}>
              ATLAS
            </span>
          </div>

          {/* Center Links */}
          <nav className="landing-nav-center">
            <span
              className={`landing-nav-link ${activeSection === 'features' ? 'active' : ''}`}
              onClick={scrollToFeatures}
            >
              Inside the Intelligence Engine
            </span>
            <span
              className={`landing-nav-link ${activeSection === 'how' ? 'active' : ''}`}
              onClick={scrollToHow}
            >
              The Path from Data to Directory
            </span>
          </nav>

          {/* Right Actions: Dark LOGIN button */}
          <div className="landing-nav-right">
            <button
              type="button"
              className="landing-login-pill"
              onClick={() => {
                setIsAuthModalOpen(true);
              }}
            >
              <span>LOGIN</span>
              <span>→</span>
            </button>
          </div>
        </div>
      </header>

      {/* CONTINUOUS SCROLLABLE CONTENT */}

      {/* 1. Hero Section */}
      <main id="hero" className="landing-hero">
        <h1 className="landing-hero-title">
          ATLAS
        </h1>

        <p className="landing-hero-subtitle">
          AI POWERED CRIMINAL NETWORK ANALYSIS SYSTEM
        </p>

        <button
          type="button"
          className="landing-cta-btn"
          onClick={handleCtaClick}
        >
          <span>BEGIN ANALYSIS</span>
          <span>→</span>
        </button>

        {/* Subtle Status Pill */}
        <div className="mt-8 flex items-center gap-2 text-xs font-medium" style={{ color: 'var(--text-faint)' }}>
          <span className="status-dot ok"></span>
          <span>Neo4j Knowledge Graph Online</span>
          <span>·</span>
          <span>{cases.length} Registered Case Dockets</span>
        </div>

        {/* Scroll Indicator Prompt */}
        <div 
          className="mt-12 flex flex-col items-center gap-1.5 cursor-pointer transition-opacity hover:opacity-100 opacity-60"
          style={{ color: 'var(--text-faint)' }}
          onClick={scrollToFeatures}
          title="Scroll down to explore platform"
        >
          <span className="text-[11px] font-semibold tracking-wider uppercase">Scroll to explore</span>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" className="animate-bounce">
            <polyline points="6 9 12 15 18 9"></polyline>
          </svg>
        </div>
      </main>

      {/* 2. Continuous Sections Container */}
      <div className="landing-sections-container">
        {/* Section 1: Inside the Intelligence Engine */}
        <section id="intelligence-engine" className="landing-kpi-section">
          <div className="landing-section-header scroll-float">
            <h2 className="landing-section-title">Inside the Intelligence Engine</h2>
          </div>

          <div className="landing-kpi-grid">
            <div className="landing-kpi-card scroll-float delay-1 floating-card-1">
              <h3 className="landing-kpi-title">Efficient Data Extraction</h3>
              <p className="landing-kpi-text">
                Seamless multi-source extraction across Police FIRs, Telecom CDR records, and Financial statements from text files, PDFs, and Excel spreadsheets.
              </p>
            </div>

            <div className="landing-kpi-card scroll-float delay-2 floating-card-2">
              <h3 className="landing-kpi-title">Graph Centrality & Shortest Path</h3>
              <p className="landing-kpi-text">
                Interactive topological graph analytics computing degree centrality, PageRank scores, and ambiguity-safe shortest path traversals.
              </p>
            </div>

            <div className="landing-kpi-card scroll-float delay-3 floating-card-3">
              <h3 className="landing-kpi-title">AI Copilot Assistant</h3>
              <p className="landing-kpi-text">
                Intelligent conversational assistant delivering instant, evidence-backed answers, cited legal deductions, and automated case summaries.
              </p>
            </div>

            <div className="landing-kpi-card scroll-float delay-4 floating-card-4">
              <h3 className="landing-kpi-title">Cross-Case Intelligence</h3>
              <p className="landing-kpi-text">
                Multi-docket network correlation detecting shared syndicates, burner devices, and money trails to drastically cut manual investigation time.
              </p>
            </div>
          </div>
        </section>

        {/* Section 2: The Path from Data to Directory */}
        <section id="data-to-directory" className="landing-kpi-section">
          <div className="landing-section-header scroll-float">
            <h2 className="landing-section-title">The Path from Data to Directory</h2>
          </div>

          <div className="landing-stepper">
            {/* Step 01 */}
            <div className="landing-step-item scroll-float delay-1 floating-card-1">
              <div className="landing-step-badge">
                <span>01</span>
              </div>
              <h3 className="landing-step-title">Upload your dataset</h3>
              <p className="landing-step-text">
                Drop Police FIRs, Telecom CDR CSVs, or banking files. We load and parse multi-source evidence into secure sessions automatically.
              </p>
            </div>

            {/* Step 02 */}
            <div className="landing-step-item scroll-float delay-2 floating-card-2">
              <div className="landing-step-badge">
                <span>02</span>
              </div>
              <h3 className="landing-step-title">Explore the graph</h3>
              <p className="landing-step-text">
                Navigate relational clusters, trace shortest paths between suspects, and uncover key operatives interactively.
              </p>
            </div>

            {/* Step 03 */}
            <div className="landing-step-item scroll-float delay-3 floating-card-3">
              <div className="landing-step-badge">
                <span>03</span>
              </div>
              <h3 className="landing-step-title">Get instant results</h3>
              <p className="landing-step-text">
                Crime graphs are mapped, centrality rankings are executed, and cross case connections are visualized in under a second.
              </p>
            </div>
          </div>
        </section>
      </div>

      {/* FOOTER */}
      <footer className="landing-footer">
        <div>ATLAS · Criminal Network Analysis System</div>
        <div style={{ color: 'var(--text-faint)' }}>Confidential Law Enforcement Information System</div>
      </footer>

      {/* LOGIN OR SIGN UP MODAL */}
      {isAuthModalOpen && (
        <div
          className="modal-overlay open"
          onClick={(e) => { if (e.target === e.currentTarget) setIsAuthModalOpen(false); }}
        >
          <div className="modal" style={{ maxWidth: '520px', padding: '24px' }}>
            <AuthModule
              isModal
              onClose={() => setIsAuthModalOpen(false)}
              setOfficerSession={setOfficerSession}
              changeView={changeView}
              addToast={addToast}
            />
          </div>
        </div>
      )}
    </div>
  );
}
