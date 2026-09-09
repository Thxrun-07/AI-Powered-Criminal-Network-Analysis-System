import React, { useState } from 'react';
import { API, Case } from '../services/api';

export interface DataIngestionModuleProps {
  fetchCases: () => Promise<Case[]>;
  changeView: (view: string) => void;
  addToast: (msg: string, type?: string) => void;
}

export function DataIngestionModule({ fetchCases, changeView, addToast }: DataIngestionModuleProps) {
  const [activeTab, setActiveTab] = useState<'json' | 'file' | 'narrative'>('json');
  const [jsonText, setJsonText] = useState<string>('');
  const [file, setFile] = useState<File | null>(null);
  const [narrativeText, setNarrativeText] = useState<string>('');
  const [ingesting, setIngesting] = useState<boolean>(false);

  const sampleJson = {
    "case_metadata": {
      "case_id": "CASE-2026-999",
      "case_name": "Operation Cyber Vault",
      "case_type": "CYBER_FRAUD",
      "priority": "HIGH",
      "status": "OPEN",
      "summary": "Extortion ring operating via spoofed banking portals and cryptowallet laundering."
    },
    "entities": {
      "people": [{ "id": "P-999", "name": "Vikram Malhotra", "status": "Suspect", "age": 34 }],
      "phones": [{ "msisdn": "+919876543210", "owner_id": "P-999", "carrier": "Airtel" }],
      "bank_accounts": [{ "account_number": "ACC999888", "owner_id": "P-999", "bank_name": "HDFC Bank" }]
    },
    "relationships": {
      "communications": [{ "caller": "+919876543210", "callee": "+919999911111", "duration_seconds": 320, "type": "VOICE_CALL" }]
    }
  };

  const handleJsonIngest = async () => {
    if (!jsonText.trim()) { addToast('Please enter JSON payload', 'info'); return; }
    setIngesting(true);
    try {
      const parsed = JSON.parse(jsonText);
      const res = await API.post<{ case_id?: string; created?: { nodes?: number } }>('/api/v1/ingest/case', parsed);
      addToast(`Successfully ingested Case '${res.case_id}'! Created ${res.created?.nodes || 0} nodes.`, 'ok');
      await fetchCases();
      changeView('cases');
    } catch (e) {
      addToast(`Ingestion error: ${(e as Error).message}`, 'err');
    } finally {
      setIngesting(false);
    }
  };

  const handleFileUpload = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!file) { addToast('Please select a file to upload', 'info'); return; }
    setIngesting(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      const res = await API.send<{ case_id?: string }>('/api/v1/ingest/file', { method: 'POST', body: formData, form: true });
      addToast(`File ingestion complete! Case ID: ${res.case_id}`, 'ok');
      await fetchCases();
      changeView('cases');
    } catch (e) {
      addToast(`Upload failed: ${(e as Error).message}`, 'err');
    } finally {
      setIngesting(false);
    }
  };

  const handleNarrativeIngest = async () => {
    if (!narrativeText.trim()) { addToast('Please enter intelligence narrative text', 'info'); return; }
    setIngesting(true);
    try {
      const formData = new FormData();
      const blob = new Blob([narrativeText], { type: 'text/plain' });
      formData.append('file', blob, 'narrative_intel.txt');
      const res = await API.send<{ case_id?: string }>('/api/v1/ingest/file', { method: 'POST', body: formData, form: true });
      addToast(`Narrative intelligence ingested for Case '${res.case_id}'!`, 'ok');
      await fetchCases();
      changeView('cases');
    } catch (e) {
      addToast(`Extraction failed: ${(e as Error).message}`, 'err');
    } finally {
      setIngesting(false);
    }
  };

  return (
    <div>
      <div className="card">
        <div className="card-header">
          <div className="card-title font-semibold text-base">Unified Multi-Source Data Ingestion Engine</div>
        </div>
        <div className="flex gap-2 border-b mb-5 pb-2.5" style={{display:'flex', gap:'8px', borderBottom:'1px solid var(--border)', marginBottom:'20px', paddingBottom:'10px'}}>
          <button className={`neu-btn transition-colors ${activeTab === 'json' ? 'primary' : 'ghost'}`} onClick={() => setActiveTab('json')}>Structured JSON Payload</button>
          <button className={`neu-btn transition-colors ${activeTab === 'file' ? 'primary' : 'ghost'}`} onClick={() => setActiveTab('file')}>Upload File (JSON / CSV)</button>
          <button className={`neu-btn transition-colors ${activeTab === 'narrative' ? 'primary' : 'ghost'}`} onClick={() => setActiveTab('narrative')}>Unstructured Text Narrative</button>
        </div>

        {activeTab === 'json' && (
          <div>
            <div className="flex justify-between items-center mb-2.5" style={{display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:'10px'}}>
              <label className="field font-bold text-xs uppercase" style={{textTransform:'uppercase', fontSize:'11.5px', fontWeight:700, color:'var(--text-dim)'}}>JSON Case Payload</label>
              <button className="neu-btn ghost transition-colors" style={{padding:'4px 8px', fontSize:'11.5px'}} onClick={() => setJsonText(JSON.stringify(sampleJson, null, 2))}>Load Sample JSON Template</button>
            </div>
            <textarea className="control mono w-full text-xs leading-relaxed" rows={16} style={{width:'100%', fontSize:'12.5px', lineHeight:1.5}} value={jsonText} onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => setJsonText(e.target.value)} placeholder="Paste Case JSON structure here..."></textarea>
            <div className="flex justify-end mt-4" style={{marginTop:'16px', display:'flex', justifyContent:'flex-end'}}>
              <button className="neu-btn primary transition-colors" disabled={ingesting} onClick={handleJsonIngest}>{ingesting ? 'Ingesting into Graph…' : 'Commit to Neo4j Knowledge Graph'}</button>
            </div>
          </div>
        )}

        {activeTab === 'file' && (
          <form onSubmit={handleFileUpload} className="flex flex-col gap-4">
            <div className="flex flex-col gap-4 items-center justify-center" style={{padding:'36px 20px', border:'2px dashed var(--border)', borderRadius:'var(--radius-sm)', textAlign:'center', marginBottom:'20px', background:'var(--bg1)'}}>
              <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="var(--text-faint)" strokeWidth="1.5" style={{marginBottom:'10px'}}><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M17 8l-5-5-5 5M12 3v12"/></svg>
              <div className="font-bold text-sm" style={{fontWeight:700, fontSize:'15px', marginBottom:'4px'}}>Select or drag & drop files</div>
              <div className="text-xs" style={{fontSize:'12.5px', color:'var(--text-faint)', marginBottom:'16px'}}>Supports structured `.json` case dossiers, CDR `.csv` phone records, bank `.csv` statements</div>
              <input type="file" onChange={(e: React.ChangeEvent<HTMLInputElement>) => setFile(e.target.files ? e.target.files[0] : null)} style={{display:'inline-block'}} />
            </div>
            <div className="flex justify-end" style={{display:'flex', justifyContent:'flex-end'}}>
              <button type="submit" className="neu-btn primary transition-colors" disabled={ingesting}>{ingesting ? 'Uploading & Extracting…' : 'Process & Upload File'}</button>
            </div>
          </form>
        )}

        {activeTab === 'narrative' && (
          <div>
            <label className="field font-bold text-xs uppercase mb-2.5 block" style={{textTransform:'uppercase', fontSize:'11.5px', fontWeight:700, color:'var(--text-dim)', marginBottom:'10px'}}>Raw Police Complaint / Informant Report Narrative</label>
            <textarea className="control w-full text-sm leading-relaxed" rows={12} style={{width:'100%', fontSize:'13.5px', lineHeight:1.6}} value={narrativeText} onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => setNarrativeText(e.target.value)} placeholder="Paste operational narrative (e.g. 'FIR lodged at Crime Branch Delhi by Complainant Smt. Sunita Devi against Suspect Rajesh Kumar regarding extortion call received from +919811122233...')..."></textarea>
            <div className="flex justify-end mt-4" style={{marginTop:'16px', display:'flex', justifyContent:'flex-end'}}>
              <button className="neu-btn primary transition-colors" disabled={ingesting} onClick={handleNarrativeIngest}>{ingesting ? 'Running LLM Extraction Engine…' : 'Extract Graph Entities via AI Engine'}</button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
