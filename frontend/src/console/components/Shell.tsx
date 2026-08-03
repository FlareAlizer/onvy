import { useEffect, useState, type ReactNode } from 'react';
import { LogOut, Menu, SlidersHorizontal, X, type LucideIcon } from 'lucide-react';
import { Logo, OnvyMark } from './Logo';
import { Avatar, Modal } from './ui';
import { FOCUS_META, useStore } from '../store';
import type { ManagerFocus } from '../types';

export interface NavItem {
  id: string;
  label: string;
  icon: LucideIcon;
  badge?: number;
}

export function Shell({
  nav,
  active,
  onNavigate,
  children,
}: {
  nav: { group: string; items: NavItem[] }[];
  active: string;
  onNavigate: (id: string) => void;
  children: ReactNode;
}) {
  const { session, logout, data, venueName, focus, setFocus } = useStore();
  const [drawer, setDrawer] = useState(false);
  const [focusOpen, setFocusOpen] = useState(false);

  useEffect(() => setDrawer(false), [active]);

  useEffect(() => {
    document.body.style.overflow = drawer ? 'hidden' : '';
    return () => {
      document.body.style.overflow = '';
    };
  }, [drawer]);

  const isRop = session?.role === 'rop';
  const point = data.points.find((p) => p.id === session?.pointId);
  const workspace = venueName || data.company?.name || '';

  const navList = (
    <nav className="flex-1 space-y-6 overflow-y-auto px-3 py-4 scroll-thin">
      {nav.map((g) => (
        <div key={g.group}>
          <p className="label mb-2 px-3">{g.group}</p>
          <ul className="space-y-0.5">
            {g.items.map((item) => {
              const Icon = item.icon;
              const on = active === item.id;
              return (
                <li key={item.id}>
                  <button
                    type="button"
                    onClick={() => onNavigate(item.id)}
                    aria-current={on ? 'page' : undefined}
                    className={`flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left text-[14px] font-medium transition ${
                      on
                        ? 'bg-brand-50 font-semibold text-brand-800'
                        : 'text-slate-600 hover:bg-slate-100 hover:text-ink'
                    }`}
                  >
                    <Icon size={17} className={on ? 'text-brand-600' : 'text-slate-500'} />
                    <span className="min-w-0 flex-1 truncate">{item.label}</span>
                    {item.badge ? (
                      <span
                        className={`num rounded-md px-1.5 py-0.5 text-[11px] font-semibold ${
                          on ? 'bg-brand-600 text-white' : 'bg-slate-200 text-slate-600'
                        }`}
                      >
                        {item.badge}
                      </span>
                    ) : null}
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
      ))}
    </nav>
  );

  /** Шапка боковой панели: продукт Onvy + рабочее пространство клиента. */
  const workspaceCard = (
    <div className="px-5 pb-3">
      <div className="rounded-lg bg-slate-50 px-3 py-2.5">
        <p className="text-[10.5px] font-semibold tracking-[0.08em] text-slate-500 uppercase">
          Рабочее пространство
        </p>
        <p className="mt-0.5 truncate text-[13px] font-semibold text-ink">{workspace}</p>
        {isRop ? (
          <button
            type="button"
            onClick={() => setFocusOpen(true)}
            className="mt-1.5 inline-flex max-w-full items-center gap-1.5 text-[11px] font-medium text-brand-700 hover:underline"
          >
            <SlidersHorizontal size={11} className="shrink-0" />
            <span className="truncate">{FOCUS_META[focus].label}</span>
          </button>
        ) : (
          <p className="mt-0.5 truncate text-[11px] text-slate-500">
            {point?.name ?? 'Кабинет сотрудника'}
          </p>
        )}
      </div>
    </div>
  );

  const footer = (
    <div className="border-t border-slate-200 p-3">
      <div className="flex items-center gap-3 rounded-lg px-2 py-2">
        <Avatar name={session?.name ?? '—'} size={34} />
        <div className="min-w-0 flex-1">
          <p className="truncate text-[13px] font-semibold text-ink">{session?.name}</p>
          <p className="truncate text-[11px] text-slate-500">{session?.position}</p>
        </div>
      </div>
      <div className="mt-1 flex gap-1">
        <button type="button" onClick={logout} className="btn-quiet flex-1 justify-start text-[13px]">
          <LogOut size={15} /> Выйти
        </button>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen lg:flex">
      <aside className="sticky top-0 hidden h-screen w-[264px] shrink-0 flex-col border-r border-slate-200 bg-white lg:flex">
        <div className="flex items-center justify-between px-5 py-4">
          <Logo />
        </div>
        {workspaceCard}
        {navList}
        {footer}
      </aside>

      {drawer && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <button
            type="button"
            aria-label="Закрыть меню"
            className="absolute inset-0 bg-ink/40"
            onClick={() => setDrawer(false)}
          />
          <div className="relative flex h-full w-[282px] max-w-[86vw] flex-col bg-white shadow-2xl">
            <div className="flex items-center justify-between px-5 py-4">
              <Logo />
              <button type="button" className="btn-quiet rounded-md p-2" onClick={() => setDrawer(false)}>
                <X size={18} />
                <span className="sr-only">Закрыть меню</span>
              </button>
            </div>
            {workspaceCard}
            {navList}
            {footer}
          </div>
        </div>
      )}

      <div className="min-w-0 flex-1">
        <header className="sticky top-0 z-30 flex items-center justify-between border-b border-slate-200 bg-white/95 px-4 py-3 backdrop-blur lg:hidden">
          <button type="button" className="btn-quiet rounded-md p-2" onClick={() => setDrawer(true)}>
            <Menu size={20} />
            <span className="sr-only">Открыть меню</span>
          </button>
          <span className="flex min-w-0 items-center gap-2">
            <OnvyMark size={24} />
            <span className="min-w-0 leading-tight">
              <span className="block text-[14px] font-semibold tracking-tight text-ink">Onvy</span>
              <span className="block truncate text-[10px] text-slate-500">{workspace}</span>
            </span>
          </span>
          <Avatar name={session?.name ?? '—'} size={30} />
        </header>

        <main className="mx-auto w-full max-w-[1320px] px-4 py-5 sm:px-6 sm:py-7 lg:px-8">{children}</main>
      </div>

      {/* Приоритеты руководителя — одна платформа, разный порядок разделов */}
      <Modal
        open={focusOpen}
        onClose={() => setFocusOpen(false)}
        title="Приоритеты руководителя"
        subtitle="Роли остаются те же. Меняется порядок разделов и то, что показывается первым."
        width="max-w-lg"
      >
        <ul className="space-y-2">
          {(Object.keys(FOCUS_META) as ManagerFocus[]).map((k) => {
            const m = FOCUS_META[k];
            const on = focus === k;
            return (
              <li key={k}>
                <button
                  type="button"
                  onClick={() => {
                    setFocus(k);
                    setFocusOpen(false);
                  }}
                  className={`w-full rounded-lg border p-3.5 text-left transition ${
                    on ? 'border-brand-500 bg-brand-50/60' : 'border-slate-200 hover:border-slate-300 hover:bg-slate-50'
                  }`}
                >
                  <span className="block text-[14px] font-semibold text-ink">{m.label}</span>
                  <span className="mt-0.5 block text-[12.5px] leading-relaxed text-slate-500">{m.hint}</span>
                </button>
              </li>
            );
          })}
        </ul>
      </Modal>
    </div>
  );
}

export function PageHead({
  title,
  subtitle,
  action,
}: {
  title: string;
  subtitle: string;
  action?: ReactNode;
}) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        <h1 className="text-[24px] leading-tight font-semibold tracking-tight text-ink sm:text-[28px]">
          {title}
        </h1>
        <p className="mt-1.5 max-w-2xl text-[14px] text-muted">{subtitle}</p>
      </div>
      {action}
    </div>
  );
}
