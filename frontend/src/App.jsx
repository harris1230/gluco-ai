import { useState } from 'react';
import { AuthProvider, useAuth } from './context/AuthContext';
import LandingPage from './pages/LandingPage';
import AuthPage from './pages/AuthPage';
import Dashboard from './pages/Dashboard';

function AppContent() {
  const { user } = useAuth();
  const [page, setPage] = useState('landing');

  if (user) return <Dashboard />;
  if (page === 'auth') return <AuthPage onBack={() => setPage('landing')} />;
  return <LandingPage onGetStarted={() => setPage('auth')} />;
}

export default function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}