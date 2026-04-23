import styles from './HistoryPanel.module.css';

function getGlucoseStatus(g) {
  if (g < 70) return { label: 'Low', color: '#ffe566' };
  if (g <= 99) return { label: 'Normal', color: '#00c8b4' };
  if (g <= 125) return { label: 'Pre-diabetic', color: '#ffa94d' };
  return { label: 'High', color: '#ff4d6d' };
}

export default function HistoryPanel({ history }) {
  if (history.length === 0) {
    return (
      <div className={styles.empty}>
        <div className={styles.emptyIcon}>◷</div>
        <h3>No scans yet</h3>
        <p>Your scan history will appear here after your first analysis.</p>
      </div>
    );
  }

  return (
    <div className={styles.panel}>
      <div className={styles.header}>
        <div className={styles.sectionLabel}>Session History</div>
        <h2 className={styles.title}>Past Scans</h2>
        <p className={styles.sub}>{history.length} scan{history.length !== 1 ? 's' : ''} this session</p>
      </div>
      <div className={styles.list}>
        {history.map((item, i) => {
          const gs = getGlucoseStatus(item.glucose);
          return (
            <div key={i} className={styles.row} style={{ animationDelay: `${i * 0.05}s` }}>
              <div className={styles.rowIndex}>#{String(history.length - i).padStart(2, '0')}</div>
              <div className={styles.rowMain}>
                <div className={styles.rowTimestamp}>{item.timestamp}</div>
                <div className={styles.rowMetrics}>
                  <span className={styles.metricChip} style={{ color: gs.color, borderColor: `${gs.color}33` }}>
                    🩸 {item.glucose} mg/dL · {gs.label}
                  </span>
                  <span className={styles.metricChip}>♥ {item.heart_rate} bpm</span>
                </div>
              </div>
              <div className={styles.miniGauge}>
                <div className={styles.miniGaugeTrack}>
                  <div className={styles.miniGaugeFill} style={{ width: `${Math.min((item.glucose / 300) * 100, 100)}%`, background: gs.color }} />
                </div>
                <div className={styles.miniGaugeLabel} style={{ color: gs.color }}>{gs.label}</div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}