import { StoreProvider } from './store';
import ROPDashboard from './views/ROPDashboard';
import EmployeeDashboard from './views/EmployeeDashboard';
import './console.css';

export type ConsoleRole = 'rop' | 'employee';

export interface ConsoleAppProps {
  role: ConsoleRole;
}

/**
 * Единая точка входа консоли речевой аналитики внутри платформы.
 *
 * В отличие от исходного App.tsx консоли, роль сюда приходит пропсом,
 * а не из её собственной сессии в localStorage: платформа уже знает роль
 * пользователя из настоящей авторизации. Стор консоли (store.tsx) пока не
 * тронут — он остаётся демо-хранилищем в localStorage, поэтому session/me
 * внутри него не связаны с реальным пользователем платформы, пока это не
 * подключат отдельно.
 */
export default function ConsoleApp({ role }: ConsoleAppProps) {
  return (
    <div className="onvy-console">
      <StoreProvider>{role === 'rop' ? <ROPDashboard /> : <EmployeeDashboard />}</StoreProvider>
    </div>
  );
}
