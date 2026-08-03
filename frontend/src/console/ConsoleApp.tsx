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
 * Единая точка входа кабинета внутри платформы.
 *
 * Роль приходит пропсом, а не из собственной сессии консоли: платформа уже знает
 * её из настоящей авторизации. Своего входа у кабинета нет и быть не должно —
 * человек уже вошёл.
 *
 * Данных кабинет не выдумывает. Экраны, подключённые к API платформы, показывают
 * настоящие цифры; остальные — пустое состояние, пока их не подключат. Раньше
 * здесь жили три демо-пространства, и вошедшего привязывали к демо-сотруднику
 * ради непустых экранов — управляющий видел чужую выручку как свою.
 */
export default function ConsoleApp({ role }: ConsoleAppProps) {
  const platformSession = getSession();
  const identity: PlatformIdentity | null = platformSession
    ? { employeeId: platformSession.employeeId, role, name: platformSession.name }
    : null;

  return (
    <div className="onvy-console">
      <StoreProvider identity={identity}>
        {role === 'rop' ? <ROPDashboard /> : <EmployeeDashboard />}
      </StoreProvider>
    </div>
  );
}
