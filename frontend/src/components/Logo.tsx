// Логотип Onvy. Вместо бинарной картинки — CSS-орб в стиле оригинала
// (положи свой jpg в src/assets/images и замени div на <img>, если нужно).

interface LogoProps {
  size?: 'sm' | 'md' | 'lg';
  showText?: boolean;
}

export default function Logo({ size = 'md', showText = true }: LogoProps) {
  const orbSizes = { sm: 'w-7 h-7', md: 'w-10 h-10', lg: 'w-20 h-20' };
  const textSizes = { sm: 'text-base gap-1.5', md: 'text-2xl gap-2.5', lg: 'text-5xl gap-5' };

  return (
    <div className={`flex items-center justify-center font-sans tracking-tight ${textSizes[size]}`}>
      <div
        className={`${orbSizes[size]} rounded-full shrink-0 shadow-[0_4px_12px_rgba(99,102,241,0.25)]`}
        style={{
          background:
            'radial-gradient(circle at 32% 28%, rgba(255,255,255,.9) 0%, rgba(255,255,255,0) 28%), conic-gradient(from 210deg, #7c3aed, #22d3ee, #ec4899, #7c3aed)',
          filter: 'saturate(1.15)',
        }}
        aria-hidden="true"
      />
      {showText && (
        <span className="font-extrabold text-zinc-950 select-none leading-none" style={{ fontWeight: 800 }}>
          Onvy
        </span>
      )}
    </div>
  );
}
