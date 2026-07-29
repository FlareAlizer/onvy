// Что показать вошедшему.
//
// Управляющий получает кабинет руководителя, остальные — кабинет сотрудника.
// Экран официанта с кнопкой рации остаётся первой вкладкой кабинета сотрудника:
// это ядро продукта в зале, и оно не должно оказаться за навигацией.

import { useState } from 'react';
import { getSession } from './lib/api';
import ConsoleApp from './console/ConsoleApp';
import EmailLoginView from './views/EmailLoginView';
import LoginView from './views/LoginView';

export default function App() {
  const session = getSession();
  const [usePin, setUsePin] = useState(false);

  if (!session) {
    return usePin ? <LoginView /> : <EmailLoginView onUsePin={() => setUsePin(true)} />;
  }

  return <ConsoleApp role={session.role === 'manager' ? 'rop' : 'employee'} />;
}
