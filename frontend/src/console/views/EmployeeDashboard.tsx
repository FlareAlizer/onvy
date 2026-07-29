import { useState } from 'react';
import { BookOpen, GraduationCap, LayoutDashboard, MessagesSquare, Radio } from 'lucide-react';
import WaiterView from '../../views/WaiterView';
import { Shell } from '../components/Shell';
import { useStore } from '../store';
import MyStats from './employee/MyStats';
import MyDialogs from './employee/MyDialogs';
import Training from './employee/Training';
import Knowledge from './Knowledge';

type Tab = 'shift' | 'stats' | 'dialogs' | 'training' | 'knowledge';

export default function EmployeeDashboard() {
  // Рация открыта первой: в зале это единственное, что нужно под рукой,
  // остальные разделы смотрят в подсобке между заказами.
  const [tab, setTab] = useState<Tab>('shift');
  const { me, data, profile } = useStore();

  const pending = me
    ? data.tests.filter((t) => t.assignedTo.includes(me.id) && (t.results[me.id] ?? 0) < t.passScore)
        .length
    : 0;

  const nav = [
    {
      group: 'Смена',
      items: [
        { id: 'shift', label: 'Рация и ассистент', icon: Radio },
        { id: 'stats', label: 'Моя смена и KPI', icon: LayoutDashboard },
        { id: 'dialogs', label: profile.labels.interactionPlural, icon: MessagesSquare },
      ],
    },
    {
      group: 'Развитие',
      items: [
        { id: 'training', label: 'Обучение', icon: GraduationCap, badge: pending || undefined },
        { id: 'knowledge', label: 'База знаний', icon: BookOpen },
      ],
    },
  ];

  return (
    <Shell nav={nav} active={tab} onNavigate={(id) => setTab(id as Tab)}>
      {tab === 'shift' && <WaiterView />}
      {tab === 'stats' && <MyStats onOpenTraining={() => setTab('training')} />}
      {tab === 'dialogs' && <MyDialogs />}
      {tab === 'training' && <Training />}
      {tab === 'knowledge' && <Knowledge role="employee" />}
    </Shell>
  );
}
