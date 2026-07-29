import { useMemo, useState } from 'react';
import {
  BookOpen,
  ChartNoAxesCombined,
  ClipboardCheck,
  LayoutDashboard,
  Sparkles,
  ListX,
  Store,
  Users,
  UsersRound,
} from 'lucide-react';
import { Shell, type NavItem } from '../components/Shell';
import { FOCUS_META, useStore } from '../store';
import Overview from './rop/Overview';
import Analytics from './rop/Analytics';
import Staff from './rop/Staff';
import TeamDevelopment from './rop/TeamDevelopment';
import TestGenerator from './rop/TestGenerator';
import Points from './rop/Points';
import PilotReport from './rop/PilotReport';
import Knowledge from './Knowledge';
import ManagerView from '../../views/ManagerView';

type Tab =
  | 'live'
  | 'overview'
  | 'analytics'
  | 'staff'
  | 'team'
  | 'tests'
  | 'knowledge'
  | 'points'
  | 'pilot';

export default function ROPDashboard() {
  const { data, profile, focus } = useStore();
  // Стоп-лист открыт первым: по спеке (S4) снять позицию с продажи должно
  // занимать секунды, а не поиск по разделам.
  const [tab, setTab] = useState<Tab>('live');
  const L = profile.labels;

  const pendingTests = data.tests.filter((t) =>
    t.assignedTo.some((id) => (t.results[id] ?? 0) < t.passScore),
  ).length;

  /**
   * Разделы одни и те же для всех руководителей — меняется только порядок.
   * Приоритет задаётся фокусом: культура, операции или продажи.
   */
  const nav = useMemo(() => {
    const items: Record<Exclude<Tab, 'live'>, NavItem> = {
      overview: { id: 'overview', label: 'Дашборд', icon: LayoutDashboard },
      analytics: { id: 'analytics', label: `Аналитика ${L.interactionGenitivePlural}`, icon: ChartNoAxesCombined },
      points: { id: 'points', label: 'Торговые точки', icon: Store, badge: data.points.length || undefined },
      staff: { id: 'staff', label: 'Сотрудники и KPI', icon: Users, badge: data.employees.length || undefined },
      team: { id: 'team', label: 'Развитие команды', icon: UsersRound },
      tests: { id: 'tests', label: 'Генератор тестов', icon: Sparkles, badge: pendingTests || undefined },
      knowledge: { id: 'knowledge', label: 'База знаний', icon: BookOpen },
      pilot: { id: 'pilot', label: 'Отчёт пилота', icon: ClipboardCheck },
    };
    const order = FOCUS_META[focus].nav as Exclude<Tab, 'live'>[];
    const primary = order.slice(0, 4).map((k) => items[k]);
    const secondary = order.slice(4).map((k) => items[k]);
    return [
      // Живая смена идёт отдельной группой сверху: это единственное здесь,
      // что работает на настоящих данных заведения прямо сейчас.
      {
        group: 'Сейчас в зале',
        items: [{ id: 'live', label: 'Стоп-лист и смена', icon: ListX } as NavItem],
      },
      { group: FOCUS_META[focus].label, items: primary },
      { group: 'Остальное', items: secondary },
    ];
  }, [focus, data.points.length, data.employees.length, pendingTests, L.interactionGenitivePlural]);

  return (
    <Shell nav={nav} active={tab} onNavigate={(id) => setTab(id as Tab)}>
      {tab === 'live' && <ManagerView />}
      {tab === 'overview' && <Overview onGoTo={(t) => setTab(t as Tab)} />}
      {tab === 'analytics' && <Analytics />}
      {tab === 'staff' && <Staff />}
      {tab === 'team' && <TeamDevelopment onGoTo={(t) => setTab(t as Tab)} />}
      {tab === 'tests' && <TestGenerator />}
      {tab === 'knowledge' && <Knowledge role="rop" />}
      {tab === 'points' && <Points />}
      {tab === 'pilot' && <PilotReport />}
    </Shell>
  );
}
