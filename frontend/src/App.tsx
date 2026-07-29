// Что показать: экран входа, регистрацию или кабинет.
//
// Управляющий получает кабинет руководителя, остальные — кабинет сотрудника.
// Экран официанта с кнопкой рации остаётся первой вкладкой кабинета сотрудника:
// это ядро продукта в зале, и оно не должно оказаться за навигацией.

import { useState } from 'react';
import { getSession } from './lib/api';
import ConsoleApp from './console/ConsoleApp';
import EmailLoginView from './views/EmailLoginView';
import LoginView from './views/LoginView';
import SignupView from './views/SignupView';

type Screen = 'email' | 'pin' | 'signup';

export default function App() {
  const session = getSession();
  const [screen, setScreen] = useState<Screen>('email');

  if (!session) {
    if (screen === 'pin') return <LoginView />;
    if (screen === 'signup') return <SignupView onBackToLogin={() => setScreen('email')} />;
    return (
      <EmailLoginView
        onUsePin={() => setScreen('pin')}
        onSignup={() => setScreen('signup')}
      />
    );
  }

  return <ConsoleApp role={session.role === 'manager' ? 'rop' : 'employee'} />;
}
