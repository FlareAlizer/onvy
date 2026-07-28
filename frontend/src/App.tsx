// Маршрутизация по роли: официант, кухня и бар получают экран рации,
// управляющий — свой. Роутера нет намеренно: на пилоте у каждого ровно один
// рабочий экран, и лишний слой навигации только мешал бы в зале.

import { getSession } from './lib/api';
import LoginView from './views/LoginView';
import ManagerView from './views/ManagerView';
import WaiterView from './views/WaiterView';

export default function App() {
  const session = getSession();

  if (!session) return <LoginView />;
  return session.role === 'manager' ? <ManagerView /> : <WaiterView />;
}
