import React, { useState } from 'react';
import { API, Case } from '../services/api';

export interface DataIngestionModuleProps {
  fetchCases: () => Promise<Case[]>;
  changeView: (view: string) => void;
  addToast: (msg: string, type?: string) => void;
}

export function DataIngestionModule({ fetchCases, changeView, addToast }: DataIngestionModuleProps) {
  const [files, setFiles] = useState<File[]>([]);
  const [ingesting, setIngesting] = useState<boolean>(false);

  const handleFileUpload = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!files || files.length === 0) {
      addToast('Please select a file to upload (.pdf, .txt, .csv, .json)', 'info');
      return;
    }

    // Validate file extensions
    const validExtensions = ['.pdf', '.txt', '.csv', '.json'];
    const invalidFiles = files.filter(f => {
      const ext = f.name.slice(f.name.lastIndexOf('.')).toLowerCase();
      return !validExtensions.includes(ext);
    });

    if (invalidFiles.length > 0) {
      addToast(`Only files of format .pdf, .txt, .csv, .json are allowed. Invalid: ${invalidFiles.map(f => f.name).join(', ')}`, 'err');
      return;
    }

    setIngesting(true);
    try {
      const formData = new FormData();
      for (const f of files) {
        formData.append('files', f);
      }
      const res = await API.send<{ case_id?: string }>('/api/v1/ingest', { method: 'POST', body: formData, form: true });
      addToast(`File ingestion complete! Case ID: ${res.case_id}`, 'ok');
      await fetchCases();
      changeView('cases');
    } catch (e) {
      addToast(`Upload failed: ${(e as Error).message}`, 'err');
    } finally {
      setIngesting(false);
    }
  };

  return (
    <div>
      <div className="card">
        <div className="card-header" style={{ marginBottom: '20px' }}>
          <div className="card-title font-semibold text-base">Multi-Source Data Ingestion Engine</div>
        </div>

        <form onSubmit={handleFileUpload} className="flex flex-col gap-4">
          <div className="flex flex-col gap-4 items-center justify-center" style={{ padding: '40px 24px', border: '2px dashed var(--border)', borderRadius: 'var(--radius-sm)', textAlign: 'center', marginBottom: '20px', background: 'var(--bg1)' }}>
            <div style={{ display: 'inline-flex', gap: '8px', marginBottom: '12px', alignItems: 'center' }}>
              <button type="button" className="neu-btn primary transition-colors" style={{ cursor: 'default', fontWeight: 600, padding: '10px 18px' }}>
                📂 Upload Document (.pdf, .json, .csv, .txt)
              </button>
            </div>
            <div className="font-bold text-base" style={{ fontWeight: 700, fontSize: '16px', marginBottom: '6px' }}>
              Select or drag & drop case files
            </div>
            <div className="text-xs mb-4 text-slate-400" style={{ fontSize: '13px', color: 'var(--text-faint)', marginBottom: '18px', maxWidth: '640px', lineHeight: 1.5 }}>
              Only files of format <strong>.pdf</strong>, <strong>.txt</strong>, <strong>.csv</strong>, and <strong>.json</strong> are allowed. Uploaded files will be automatically parsed and converted to the exact standardized Case JSON format without hallucination or unnecessary repetition of data.
            </div>
            <input
              type="file"
              accept=".pdf,.txt,.csv,.json"
              multiple
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => setFiles(Array.from(e.target.files || []))}
              style={{ display: 'inline-block' }}
            />
            {files.length > 0 && (
              <div className="mt-3 text-sm font-semibold text-atlas-cyan" style={{ marginTop: '14px', fontSize: '13.5px', color: 'var(--accent)', fontWeight: 600 }}>
                Selected {files.length} file{files.length > 1 ? 's' : ''}: {files.map(f => f.name).join(', ')}
              </div>
            )}
          </div>
          <div className="flex justify-end" style={{ display: 'flex', justifyContent: 'flex-end' }}>
            <button type="submit" className="neu-btn primary transition-colors" disabled={ingesting || files.length === 0}>
              {ingesting ? 'Uploading & Extracting…' : 'Process & Upload File'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
