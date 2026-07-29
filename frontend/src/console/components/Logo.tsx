import { useId } from 'react';

/**
 * Фирменный знак Onvy — сфера с мягкими переливами.
 * Если у вас есть исходный PNG/SVG, положите его в /public/logo.svg
 * и замените тело OnvyMark на <img src="/logo.svg" />.
 */
export function OnvyMark({ size = 32, className = '' }: { size?: number; className?: string }) {
  const id = useId().replace(/:/g, '');
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 120 120"
      className={className}
      aria-hidden
      role="presentation"
    >
      <defs>
        <clipPath id={`${id}-clip`}>
          <circle cx="60" cy="60" r="54" />
        </clipPath>
        <radialGradient id={`${id}-base`} cx="42%" cy="38%" r="72%">
          <stop offset="0%" stopColor="#ffffff" />
          <stop offset="45%" stopColor="#f2ecff" />
          <stop offset="100%" stopColor="#dcd2fb" />
        </radialGradient>
        <filter id={`${id}-soft`} x="-60%" y="-60%" width="220%" height="220%">
          <feGaussianBlur stdDeviation="13" />
        </filter>
        <filter id={`${id}-glow`} x="-40%" y="-40%" width="180%" height="180%">
          <feGaussianBlur stdDeviation="6" />
        </filter>
      </defs>

      {/* Мягкое свечение вокруг сферы */}
      <circle cx="60" cy="60" r="52" fill="#c9b8f7" opacity="0.32" filter={`url(#${id}-glow)`} />

      <g clipPath={`url(#${id}-clip)`}>
        <circle cx="60" cy="60" r="54" fill={`url(#${id}-base)`} />

        {/* Цветные доли: маджента слева, синий в центре, лиловый справа */}
        <g filter={`url(#${id}-soft)`}>
          <ellipse cx="16" cy="62" rx="26" ry="42" fill="#f83fd0" opacity="0.85" />
          <ellipse cx="34" cy="52" rx="30" ry="46" fill="#7aa8ff" opacity="0.9" />
          <ellipse cx="52" cy="86" rx="34" ry="30" fill="#5b8dff" opacity="0.7" />
          <ellipse cx="86" cy="58" rx="30" ry="44" fill="#b98cff" opacity="0.85" />
          <ellipse cx="104" cy="44" rx="24" ry="30" fill="#ffffff" opacity="0.9" />
          <ellipse cx="74" cy="30" rx="26" ry="20" fill="#ffffff" opacity="0.8" />
          <ellipse cx="62" cy="104" rx="30" ry="16" fill="#ffffff" opacity="0.55" />
        </g>

        {/* Меридиан — намёк на объём сферы */}
        <ellipse
          cx="60"
          cy="60"
          rx="22"
          ry="53"
          fill="none"
          stroke="#ffffff"
          strokeWidth="3"
          opacity="0.5"
          filter={`url(#${id}-glow)`}
        />
        <ellipse cx="78" cy="58" rx="30" ry="52" fill="none" stroke="#ffffff" strokeWidth="2" opacity="0.35" />

        {/* Блик */}
        <ellipse cx="44" cy="26" rx="20" ry="10" fill="#ffffff" opacity="0.6" filter={`url(#${id}-glow)`} />
      </g>
    </svg>
  );
}

/**
 * Знак плюс словесный логотип. `workspace` показывает,
 * в чьём рабочем пространстве находится пользователь: Onvy / Чайхона №1.
 */
export function Logo({
  size = 30,
  withWordmark = true,
  workspace,
  invert = false,
}: {
  size?: number;
  withWordmark?: boolean;
  workspace?: string;
  invert?: boolean;
}) {
  return (
    <span className="inline-flex min-w-0 items-center gap-2.5">
      <OnvyMark size={size} />
      {withWordmark && (
        <span className="min-w-0 leading-tight">
          <span
            className={`block text-[19px] font-semibold tracking-tight ${
              invert ? 'text-white' : 'text-ink'
            }`}
          >
            Onvy
          </span>
          {workspace && (
            <span
              className={`block truncate text-[11px] font-medium ${invert ? 'text-slate-500' : 'text-slate-500'}`}
            >
              {workspace}
            </span>
          )}
        </span>
      )}
    </span>
  );
}
