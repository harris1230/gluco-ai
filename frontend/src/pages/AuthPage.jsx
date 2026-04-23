import { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { api } from '../api';
import styles from './AuthPage.module.css';

export default function AuthPage({ onBack }) {
  const { login } = useAuth();
  const [mode, setMode] = useState('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const handle = async (e) => {
    e.preventDefault();
    setError(''); setSuccess('');
    if (mode === 'signup' && password !== confirm) { setError('Passwords do not match.'); return; }
    setLoading(true);
    try {
      if (mode === 'signup') {
        const data = await api.signup(email, password);
        if (data.error) { setError(data.error); return; }
        setSuccess('Account created! Signing you in…');
        const loginData = await api.login(email, password);
        if (loginData.message) login(email);
        else setError(loginData.error || 'Login failed');
      } else {
        const data = await api.login(email, password);
        if (data.message) login(email);
        else setError(data.error || 'Invalid credentials');
      }
    } catch { setError('Network error. Is the backend running?'); }
    finally { setLoading(false); }
  };

  return (
    <div className={styles.page}>
      <div className={styles.glow} />
      <button className={styles.back} onClick={onBack}>← Back</button>

      <div className={styles.card}>
        <div className={styles.left}>
          <div className={styles.leftInner}>
            <div className={styles.logo}>
              <span className={styles.logoIcon}>⬡</span>
              GlucoScan<span className={styles.logoAi}>AI</span>
            </div>
            <h2 className={styles.leftTitle}>
              Non-invasive glucose<br />
              <span className={styles.serif}>monitoring, reimagined.</span>
            </h2>
            <ul className={styles.features}>
              {['Upload finger video', 'PPG signal extraction', 'LSTM glucose prediction', 'Instant waveform graph'].map(f => (
                <li key={f}><span className={styles.tick}>✓</span> {f}</li>
              ))}
            </ul>
            <div className={styles.disclaimer}>⚠️ Experimental AI only. Not a medical device.</div>
          </div>
        </div>

        <div className={styles.right}>
          <div className={styles.toggle}>
            <button className={`${styles.toggleBtn} ${mode === 'login' ? styles.active : ''}`} onClick={() => { setMode('login'); setError(''); }}>Sign In</button>
            <button className={`${styles.toggleBtn} ${mode === 'signup' ? styles.active : ''}`} onClick={() => { setMode('signup'); setError(''); }}>Create Account</button>
          </div>

          <h1 className={styles.formTitle}>{mode === 'login' ? 'Welcome back' : 'Get started'}</h1>
          <p className={styles.formSub}>{mode === 'login' ? 'Enter your credentials to access your dashboard.' : 'Create your account to start scanning.'}</p>

          {error && <div className={styles.alert} data-type="error"><span>⚠</span> {error}</div>}
          {success && <div className={styles.alert} data-type="success"><span>✓</span> {success}</div>}

          <form onSubmit={handle} className={styles.form}>
            <div className={styles.field}>
              <label className={styles.label}>Email</label>
              <input type="email" className={styles.input} placeholder="you@example.com" value={email} onChange={e => setEmail(e.target.value)} required />
            </div>
            <div className={styles.field}>
              <label className={styles.label}>Password</label>
              <input type="password" className={styles.input} placeholder="••••••••" value={password} onChange={e => setPassword(e.target.value)} required />
            </div>
            {mode === 'signup' && (
              <div className={styles.field}>
                <label className={styles.label}>Confirm Password</label>
                <input type="password" className={styles.input} placeholder="••••••••" value={confirm} onChange={e => setConfirm(e.target.value)} required />
              </div>
            )}
            <button type="submit" className={styles.submit} disabled={loading}>
              {loading ? <span className={styles.spinner} /> : mode === 'login' ? 'Sign In →' : 'Create Account →'}
            </button>
          </form>

          <p className={styles.switchText}>
            {mode === 'login' ? "Don't have an account? " : 'Already have an account? '}
            <button className={styles.switchBtn} onClick={() => { setMode(mode === 'login' ? 'signup' : 'login'); setError(''); }}>
              {mode === 'login' ? 'Sign up' : 'Sign in'}
            </button>
          </p>
        </div>
      </div>
    </div>
  );
}