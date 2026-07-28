import { useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import type { Session } from './types';
import { getSession, clearSession } from './lib/api';

import AuthView from './views/AuthView';
import ROPDashboard from './views/ROPDashboard';
import EmployeeDashboard from './views/EmployeeDashboard';

export default function App() {
  // Сессия переживает перезагрузку страницы (localStorage).
  const [session, setSession] = useState<Session | null>(() => getSession());

  const handleLogout = () => {
    clearSession();
    setSession(null);
  };

  return (
    <div className="h-screen w-screen overflow-hidden flex flex-col bg-white">
      <AnimatePresence mode="wait">
        {!session ? (
          <motion.div key="auth" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="flex-1 flex">
            <AuthView onLogin={setSession} />
          </motion.div>
        ) : (
          <motion.div key="dashboard" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="flex h-full w-full">
            {session.role === 'manager' ? (
              <ROPDashboard session={session} onLogout={handleLogout} />
            ) : (
              <EmployeeDashboard session={session} onLogout={handleLogout} />
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
