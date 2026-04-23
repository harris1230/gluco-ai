import styles from './ResultsPanel.module.css';

function getGlucoseStatus(g) {
  if (g < 70) return { label: 'Low', color: '#ffe566', emoji: '⬇' };
  if (g <= 99) return { label: 'Normal', color: '#00c8b4', emoji: '✓' };
  if (g <= 125) return { label: 'Pre-diabetic', color: '#ffa94d', emoji: '⚠' };
  return { label: 'High', color: '#ff4d6d', emoji: '⬆' };
}
function getHRStatus(hr) {
  if (hr < 60) return { label: 'Low', color: '#ffe566' };
  if (hr <= 100) return { label: 'Normal', color: '#00c8b4' };
  return { label: 'Elevated', color: '#ffa94d' };
}

export default function ResultsPanel({ results }) {
  const { heart_rate, glucose, status, graph } = results;
  const gStatus = getGlucoseStatus(glucose);
  const hrStatus = getHRStatus(heart_rate);
  const gaugePercent = Math.min((glucose / 300) * 100, 100);
  const heights = [4, 4, 8, 20, 40, 20, 8, 4, 4, 4, 4, 8, 24, 44, 24, 8, 4, 4, 4, 4];

  return (
    <div className={styles.panel}>
      <div className={styles.header}>
        <div className={styles.sectionLabel}>Analysis Complete</div>
        <h2 className={styles.title}>Results</h2>
        <div className={styles.statusBadge}><span className={styles.statusDot} />{status}</div>
      </div>

      <div className={styles.metrics}>
        {/* Glucose */}
        <div className={styles.metricCard} style={{ '--card-color': gStatus.color }}>
          <div className={styles.metricHeader}><span className={styles.metricIcon}>🩸</span><span className={styles.metricLabel}>Blood Glucose</span></div>
          <div className={styles.metricValue}>{glucose}<span className={styles.metricUnit}>mg/dL</span></div>
          <div className={styles.metricStatus} style={{ color: gStatus.color }}><span>{gStatus.emoji}</span> {gStatus.label}</div>
          <div className={styles.gauge}>
            <div className={styles.gaugeTrack}>
              <div className={styles.gaugeFill} style={{ width: `${gaugePercent}%`, background: gStatus.color }} />
            </div>
            <div className={styles.gaugeLabels}><span>0</span><span>70</span><span>100</span><span>126</span><span>300</span></div>
          </div>
          <div className={styles.reference}>
            <span style={{ color: '#ffe566' }}>■</span> &lt;70 Low &nbsp;
            <span style={{ color: '#00c8b4' }}>■</span> 70–99 Normal &nbsp;
            <span style={{ color: '#ffa94d' }}>■</span> 100–125 Pre &nbsp;
            <span style={{ color: '#ff4d6d' }}>■</span> ≥126 High
          </div>
        </div>

        {/* Heart Rate */}
        <div className={styles.metricCard} style={{ '--card-color': hrStatus.color }}>
          <div className={styles.metricHeader}><span className={styles.metricIcon}>♥</span><span className={styles.metricLabel}>Heart Rate</span></div>
          <div className={styles.metricValue}>{heart_rate}<span className={styles.metricUnit}>bpm</span></div>
          <div className={styles.metricStatus} style={{ color: hrStatus.color }}>{hrStatus.label}</div>
          <div className={styles.pulseAnim}>
            {heights.map((h, i) => (
              <div key={i} className={styles.pulseBeat} style={{ height: `${h}px`, background: hrStatus.color, animationDelay: `${i * 0.05}s` }} />
            ))}
          </div>
          <div className={styles.reference}>
            <span style={{ color: '#ffe566' }}>■</span> &lt;60 Low &nbsp;
            <span style={{ color: '#00c8b4' }}>■</span> 60–100 Normal &nbsp;
            <span style={{ color: '#ffa94d' }}>■</span> &gt;100 Elevated
          </div>
        </div>
      </div>

      {graph && (
        <div className={styles.graphSection}>
          <div className={styles.graphLabel}>PPG Waveform</div>
          <div className={styles.graphWrap}>
            <img src={`data:image/png;base64,${graph}`} alt="PPG Signal Graph" className={styles.graph} />
          </div>
        </div>
      )}

      <div className={styles.disclaimer}>
        <span>⚠️</span>
        <p>This is an <strong>experimental AI prediction</strong> and should not be used for medical decisions. Always consult a healthcare professional and use a certified glucometer for accurate readings.</p>
      </div>
    </div>
  );
}