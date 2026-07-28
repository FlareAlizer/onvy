// Крупный переключатель для стоп-листа (spec S4): вся строка — цель нажатия,
// а не только сам тумблер, потому что действие должно занимать секунды и
// попадать под палец с первого раза, даже если рука занята подносом.

export function Toggle({ checked }: { checked: boolean }) {
  return (
    <span
      aria-hidden="true"
      className={`relative inline-flex h-8 w-14 shrink-0 items-center rounded-full transition-colors duration-150 ease-out ${
        checked ? 'bg-red-500' : 'bg-stone-700'
      }`}
    >
      <span
        className={`inline-block h-6 w-6 transform rounded-full bg-stone-50 shadow transition-transform duration-150 ease-out ${
          checked ? 'translate-x-7' : 'translate-x-1'
        }`}
      />
    </span>
  );
}
