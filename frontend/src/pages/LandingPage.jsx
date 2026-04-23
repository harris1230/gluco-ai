import styles from './LandingPage.module.css';

export default function LandingPage({ onGetStarted }) {
  return (
    <div className={styles.page}>
      <div className={styles.glow1} />
      <div className={styles.glow2} />

      <nav className={styles.nav}>
        <div className={styles.logo}>
          <span className={styles.logoIcon}>⬡</span>
          GlucoScan<span className={styles.logoAi}>AI</span>
        </div>
        <button className={styles.navCta} onClick={onGetStarted}>Get Started →</button>
      </nav>

      <section className={styles.hero}>
        <div className={styles.badge}>
          <span className={styles.badgeDot} />
          Experimental · Non-Invasive · AI-Powered
        </div>
        <h1 className={styles.heroTitle}>
          Monitor Glucose<br />
          <span className={styles.heroAccent}>Without a Needle</span>
        </h1>
        <p className={styles.heroSub}>
          Upload a short finger video. Our LSTM model extracts your PPG signal
          and predicts blood glucose levels — all in seconds.
        </p>
        <div className={styles.heroCtas}>
          <button className={styles.ctaPrimary} onClick={onGetStarted}>
            <span>Start Scanning</span><span className={styles.ctaArrow}>→</span>
          </button>
          <a href="#how" className={styles.ctaSecondary}>How it works ↓</a>
        </div>
        <div className={styles.statCards}>
          {[
            { val: '< 5s', label: 'Analysis time' },
            { val: 'LSTM', label: 'Neural model' },
            { val: 'PPG', label: 'Signal source' },
          ].map((s) => (
            <div key={s.label} className={styles.statCard}>
              <div className={styles.statVal}>{s.val}</div>
              <div className={styles.statLabel}>{s.label}</div>
            </div>
          ))}
        </div>
      </section>

      <div className={styles.pulseWrap}>
        <div className={styles.pulseRing} />
        <div className={styles.pulseRing} style={{ animationDelay: '0.6s' }} />
        <div className={styles.pulseRing} style={{ animationDelay: '1.2s' }} />
        <div className={styles.pulseCore}>
          <span className={styles.heartIcon}>♥</span>
        </div>
      </div>

      <section className={styles.how} id="how">
        <div className={styles.sectionLabel}>Process</div>
        <h2 className={styles.sectionTitle}>How it works</h2>
        <div className={styles.steps}>
          {[
            { n: '01', title: 'Record Video', desc: 'Place your fingertip on the rear camera for 30 seconds under good light.' },
            { n: '02', title: 'Extract PPG', desc: 'We extract photoplethysmography signals from frame-level RGB data.' },
            { n: '03', title: 'AI Analysis', desc: 'Our bidirectional LSTM predicts glucose from the cleaned PPG waveform.' },
            { n: '04', title: 'Get Results', desc: 'Receive heart rate, glucose estimate, and a full waveform graph.' },
          ].map((s, i) => (
            <div key={s.n} className={styles.step} style={{ animationDelay: `${i * 0.1}s` }}>
              <div className={styles.stepNum}>{s.n}</div>
              <h3 className={styles.stepTitle}>{s.title}</h3>
              <p className={styles.stepDesc}>{s.desc}</p>
            </div>
          ))}
        </div>
      </section>

      <section className={styles.ctaBanner}>
        <h2>Ready to scan?</h2>
        <p>Create a free account and run your first analysis in under a minute.</p>
        <button className={styles.ctaPrimary} onClick={onGetStarted}>
          <span>Create Account</span><span className={styles.ctaArrow}>→</span>
        </button>
      </section>

      <footer className={styles.footer}>
        <span className={styles.logo}>
          <span className={styles.logoIcon}>⬡</span> GlucoScan AI
        </span>
        <span className={styles.footerNote}>⚠️ Experimental. Not a medical device.</span>
      </footer>
    </div>
  );
}