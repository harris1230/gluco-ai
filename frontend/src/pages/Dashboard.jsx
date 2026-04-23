import { useState } from 'react';
import Navbar from '../components/Navbar';
import UploadPanel from '../components/UploadPanel';
import ResultsPanel from '../components/ResultsPanel';
import HistoryPanel from '../components/HistoryPanel';
import styles from './Dashboard.module.css';

export default function Dashboard() {
  const [tab, setTab] = useState('scan');
  const [results, setResults] = useState(null);
  const [history, setHistory] = useState([]);

  const handleResults = (data) => {
    setResults(data);
    setHistory(prev => [{ ...data, timestamp: new Date().toLocaleString() }, ...prev].slice(0, 20));
  };

  return (
    <div className={styles.page}>
      <div className={styles.glow1} /><div className={styles.glow2} />
      <Navbar />
      <div className={styles.tabs}>
        <button className={`${styles.tab} ${tab === 'scan' ? styles.active : ''}`} onClick={() => setTab('scan')}>
          <span className={styles.tabIcon}>⬡</span> Scan
        </button>
        <button className={`${styles.tab} ${tab === 'history' ? styles.active : ''}`} onClick={() => setTab('history')}>
          <span className={styles.tabIcon}>◷</span> History
          {history.length > 0 && <span className={styles.badge}>{history.length}</span>}
        </button>
      </div>
      <main className={styles.main}>
        {tab === 'scan' && (
          <div className={styles.scanLayout}>
            <UploadPanel onResults={handleResults} />
            {results && <ResultsPanel results={results} />}
          </div>
        )}
        {tab === 'history' && <HistoryPanel history={history} />}
      </main>
    </div>
  );
}