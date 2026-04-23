import { useState, useRef } from 'react';
import { api } from '../api';
import styles from './UploadPanel.module.css';

export default function UploadPanel({ onResults }) {
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [drag, setDrag] = useState(false);
  const [progress, setProgress] = useState(0);
  const inputRef = useRef();

  const handleFile = (f) => {
    if (!f) return;
    if (!f.type.startsWith('video/')) { setError('Please upload a video file.'); return; }
    setFile(f); setError('');
  };

  const handleDrop = (e) => { e.preventDefault(); setDrag(false); handleFile(e.dataTransfer.files[0]); };

  const handleSubmit = async () => {
    if (!file) return;
    setLoading(true); setError(''); setProgress(0);
    const interval = setInterval(() => setProgress(p => p < 85 ? p + Math.random() * 8 : p), 400);
    try {
      const data = await api.predict(file);
      clearInterval(interval); setProgress(100);
      if (data.error) { setError(data.error); setProgress(0); }
      else { onResults(data); setFile(null); setTimeout(() => setProgress(0), 1000); }
    } catch { clearInterval(interval); setProgress(0); setError('Failed to connect to the server.'); }
    finally { setLoading(false); }
  };

  const steps = ['Extracting frames', 'Computing PPG signal', 'Filtering & smoothing', 'Running LSTM model'];
  const stepIdx = Math.min(Math.floor((progress / 100) * steps.length), steps.length - 1);

  return (
    <div className={styles.panel}>
      <div className={styles.header}>
        <div className={styles.sectionLabel}>New Scan</div>
        <h2 className={styles.title}>Upload Finger Video</h2>
        <p className={styles.sub}>Record your fingertip pressed on the rear camera for ~30 seconds under good lighting.</p>
      </div>

      <div className={styles.tips}>
        {[{ icon: '☀️', tip: 'Use good lighting' }, { icon: '🤏', tip: 'Steady pressure on lens' }, { icon: '⏱', tip: 'Minimum 15 seconds' }, { icon: '🔋', tip: 'Flash ON recommended' }].map(t => (
          <div key={t.tip} className={styles.tip}><span>{t.icon}</span> {t.tip}</div>
        ))}
      </div>

      <div
        className={`${styles.dropZone} ${drag ? styles.dragging : ''} ${file ? styles.hasFile : ''}`}
        onClick={() => !loading && inputRef.current.click()}
        onDragOver={e => { e.preventDefault(); setDrag(true); }}
        onDragLeave={() => setDrag(false)}
        onDrop={handleDrop}
      >
        <input ref={inputRef} type="file" accept="video/*" style={{ display: 'none' }} onChange={e => handleFile(e.target.files[0])} />
        {file ? (
          <div className={styles.fileInfo}>
            <div className={styles.fileIcon}>▶</div>
            <div>
              <div className={styles.fileName}>{file.name}</div>
              <div className={styles.fileSize}>{(file.size / 1024 / 1024).toFixed(2)} MB</div>
            </div>
            <button className={styles.removeFile} onClick={e => { e.stopPropagation(); setFile(null); }}>✕</button>
          </div>
        ) : (
          <div className={styles.dropContent}>
            <div className={styles.dropIconWrap}><span className={styles.dropIcon}>⬆</span></div>
            <div className={styles.dropText}><strong>Drop video here</strong> or click to browse</div>
            <div className={styles.dropHint}>MP4, MOV, AVI · Max 100MB</div>
          </div>
        )}
      </div>

      {error && <div className={styles.error}><span>⚠</span> {error}</div>}

      {loading && (
        <div className={styles.progressWrap}>
          <div className={styles.progressBar}>
            <div className={styles.progressFill} style={{ width: `${progress}%` }} />
          </div>
          <div className={styles.progressStep}>
            <span className={styles.progressDot} />{steps[stepIdx]}…
          </div>
        </div>
      )}

      <button className={styles.analyzeBtn} onClick={handleSubmit} disabled={!file || loading}>
        {loading ? <><span className={styles.spinner} /> Analyzing…</> : <><span>⬡</span> Analyze Video</>}
      </button>
    </div>
  );
}