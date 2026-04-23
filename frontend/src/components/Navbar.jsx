import { useAuth } from '../context/AuthContext';
import styles from './Navbar.module.css';

export default function Navbar() {
  const { user, logout } = useAuth();
  return (
    <nav className={styles.nav}>
      <div className={styles.logo}>
        <span className={styles.logoIcon}>⬡</span>
        GlucoScan<span className={styles.logoAi}>AI</span>
      </div>
      <div className={styles.right}>
        {user && (
          <div className={styles.userInfo}>
            <div className={styles.avatar}>{user.email[0].toUpperCase()}</div>
            <span className={styles.email}>{user.email}</span>
          </div>
        )}
        <button className={styles.logoutBtn} onClick={logout}>Sign Out</button>
      </div>
    </nav>
  );
}