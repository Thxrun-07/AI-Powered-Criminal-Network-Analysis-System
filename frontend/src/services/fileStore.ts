// Storage and retrieval service for uploaded case files and evidence documents

export interface UploadedCaseFile {
  id: string;
  case_id: string;
  file_name: string;
  file_type: 'pdf' | 'csv' | 'txt' | 'document';
  file_size: string;
  uploaded_at: string;
  content: string;
  sha256?: string;
}

const STORAGE_KEY = 'atlas_uploaded_case_files_v1';

export const FileStore = {
  getAll(): UploadedCaseFile[] {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return [];
      return JSON.parse(raw);
    } catch {
      return [];
    }
  },

  getByCaseId(caseId: string): UploadedCaseFile[] {
    const all = this.getAll();
    return all.filter(f => f.case_id.toLowerCase() === caseId.toLowerCase());
  },

  saveFile(file: Omit<UploadedCaseFile, 'id'>): UploadedCaseFile {
    const all = this.getAll();
    const newFile: UploadedCaseFile = {
      ...file,
      id: `file_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`
    };
    // Replace if same case and filename, otherwise append
    const filtered = all.filter(
      f => !(f.case_id.toLowerCase() === file.case_id.toLowerCase() && f.file_name.toLowerCase() === file.file_name.toLowerCase())
    );
    filtered.unshift(newFile);
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(filtered));
    } catch (e) {
      console.warn('LocalStorage limit reached for file store', e);
    }
    return newFile;
  },

  deleteFile(fileId: string): void {
    const all = this.getAll().filter(f => f.id !== fileId);
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(all));
    } catch (e) {
      console.warn('Failed to delete file from store', e);
    }
  },

  formatBytes(bytes: number, decimals = 1): string {
    if (!+bytes) return '0 B';
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(dm))} ${sizes[i]}`;
  }
};

const LOCAL_CASES_KEY = 'atlas_local_cases_v1';

export const LocalCaseStore = {
  getAll(): any[] {
    try {
      const raw = localStorage.getItem(LOCAL_CASES_KEY);
      if (!raw) return [];
      return JSON.parse(raw);
    } catch {
      return [];
    }
  },

  saveCase(c: any): void {
    const all = this.getAll();
    const existingIndex = all.findIndex(item => (item.case_id || '').toLowerCase() === (c.case_id || '').toLowerCase());
    if (existingIndex >= 0) {
      all[existingIndex] = { ...all[existingIndex], ...c };
    } else {
      all.unshift(c);
    }
    try {
      localStorage.setItem(LOCAL_CASES_KEY, JSON.stringify(all));
    } catch (e) {
      console.warn('Failed to save local case', e);
    }
  },

  deleteCase(caseId: string): void {
    const all = this.getAll().filter(item => (item.case_id || '').toLowerCase() !== (caseId || '').toLowerCase());
    try {
      localStorage.setItem(LOCAL_CASES_KEY, JSON.stringify(all));
    } catch (e) {
      console.warn('Failed to delete local case', e);
    }
  }
};

