import { getSession } from '../lib/api';
import { StoreProvider, type PlatformIdentity } from './store';
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
 * пользователя из настоящей авторизации. Стор консоли (store.tsx) остаётся
 * демо-хранилищем, но теперь получает identity — роль и имя настоящего
 * вошедшего — и сам находит для него подходящего демо-человека, чтобы
 * `me`/`session` внутри не оказывались null (см. store.tsx: identityAccount).
 * Статистика на её экранах при этом остаётся демонстрационной — реальные
 * данные сотрудника к этой консоли пока не подключены (отдельная задача).
 */
export default function ConsoleApp({ role }: ConsoleAppProps) {
  const platformSession = getSession();
  const identity: PlatformIdentity | null = platformSession
    ? { role, name: platformSession.name }
    : null;

  return (
    <div className="onvy-console">
      <StoreProvider identity={identity}>
        {role === 'rop' ? <ROPDashboard /> : <EmployeeDashboard />}
      </StoreProvider>
    </div>
  );
}
