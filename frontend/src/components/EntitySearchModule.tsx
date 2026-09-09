import React, { useState } from 'react';
import { API, esc, Entity } from '../services/api';

export interface EntitySearchModuleProps {
  openEntityModal: (id: string) => void;
  addToast: (msg: string, type?: string) => void;
}

export function EntitySearchModule({ openEntityModal, addToast }: EntitySearchModuleProps) {
  const [query, setQuery] = useState<string>('');
  const [category, setCategory] = useState<string>('');
  const [results, setResults] = useState<Entity[] | null>(null);
  const [loading, setLoading] = useState<boolean>(false);

  const doSearch = async (): Promise<void> => {
    if (!query.trim()) {
      addToast('Please specify a search query', 'info');
      return;
    }
    setLoading(true);
    try {
      const res = await API.get<Entity[]>(
        `/api/entities/search?q=${encodeURIComponent(query.trim())}${category ? `&entity_type=${category}` : ''}&limit=50`
      );
      setResults(res);
    } catch (e: unknown) {
      setResults([]);
      const errMsg = e instanceof Error ? e.message : String(e);
      addToast(errMsg, 'err');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <div className="card">
        <div className="card-header">
          <div className="card-title">Entity Knowledge Search</div>
        </div>
        <div className="row flex gap-3.5 items-end flex-wrap" style={{ alignItems: 'flex-end' }}>
          <div className="field flex-1" style={{ flex: 2 }}>
            <label>Search Query</label>
            <input
              className="control"
              value={query}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => setQuery(e.target.value)}
              onKeyDown={(e: React.KeyboardEvent<HTMLInputElement>) => {
                if (e.key === 'Enter') doSearch();
              }}
              placeholder="Enter name, phone (+91...), account number, VIN, license plate, or handle…"
            />
          </div>
          <div className="field max-w-[200px]" style={{ maxWidth: '200px' }}>
            <label>Entity Category</label>
            <select
              className="control"
              value={category}
              onChange={(e: React.ChangeEvent<HTMLSelectElement>) => setCategory(e.target.value)}
            >
              <option value="">All Categories</option>
              {['Person', 'Phone', 'BankAccount', 'Vehicle', 'SocialHandle', 'IPAddress', 'Location', 'CellTower', 'Case', 'FIR'].map((t) => (
                <option key={t}>{t}</option>
              ))}
            </select>
          </div>
          <button className="neu-btn primary flex items-center gap-2 transition" disabled={loading} onClick={doSearch}>
            <svg viewBox="0 0 24 24" fill="none" strokeWidth="2" strokeLinecap="round">
              <path d="M11 19a8 8 0 1 0 0-16 8 8 0 0 0 0 16Zm10 2-4.35-4.35" />
            </svg>
            Search
          </button>
        </div>
      </div>

      <div className="card">
        <div className="card-header flex items-center justify-between">
          <div className="card-title">Search Results</div>
          <span className="tag plain">{results ? `${results.length} matches` : '0 matches'}</span>
        </div>
        {loading ? (
          <div>
            <div className="skeleton sk-row"></div>
            <div className="skeleton sk-row"></div>
          </div>
        ) : !results ? (
          <div className="empty">
            <svg viewBox="0 0 24 24" fill="none" strokeWidth="2">
              <path d="M11 19a8 8 0 1 0 0-16 8 8 0 0 0 0 16Zm10 2-4.35-4.35" />
            </svg>
            Execute a search query above to inspect entity profiles.
          </div>
        ) : !results.length ? (
          <div className="empty">No entity matches found for "{query}". Try searching by partial name or number.</div>
        ) : (
          <div>
            {results.map((r) => {
              const entityId = r.entity_id || r.id || '';
              const displayName = r.display_name || r.name || entityId;
              const labels = r.labels || [];
              return (
                <div
                  key={entityId}
                  className="result-item flex items-center justify-between cursor-pointer hover:bg-[var(--surface-hover)] transition"
                  onClick={() => openEntityModal(entityId)}
                >
                  <div className="result-main">
                    <div className="result-name font-semibold">{esc(displayName)}</div>
                    <div className="result-sub mono text-xs">{esc(entityId)}</div>
                  </div>
                  <div className="flex items-center gap-2.5" style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <span className="tag plain">{labels.slice(0, 3).join(', ')}</span>
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth="2" strokeLinecap="round">
                      <path d="M9 6l6 6-6 6" />
                    </svg>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
