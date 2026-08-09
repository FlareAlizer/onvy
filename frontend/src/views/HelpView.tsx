// Справка «Как это работает» — открывается из кабинета сотрудника и из
// кабинета управляющего. Читают официанты и повара: в шумном зале, часто не
// на родном русском, между заказами. Короткие фразы и примеры того, что
// сказать вслух — не техническая документация.
//
// Источник правды для каждого утверждения на странице:
//   app/domain/intents.py         — как распознаётся обращение по имени/отделу
//   app/api/voice.py _should_redirect — «Онви» вслух сильнее выбора на экране
//   app/services/dispatch.py + tests/test_dispatch_privacy.py — кто услышит
//   app/domain/text.py            — падежи и опечатки распознавания
//   app/adapters/yandex/answer.py — честный ответ про аллергены
//   frontend/src/views/WaiterView.tsx — что реально видно на экране официанта

import type { ReactNode } from 'react';
import type { LucideIcon } from 'lucide-react';
import {
  AlertTriangle,
  CircleHelp,
  EyeOff,
  Lock,
  ShieldCheck,
  Sparkles,
  UtensilsCrossed,
  Users,
  WifiOff,
} from 'lucide-react';
import { PageHead } from '../console/components/Shell';
import { Card, SectionHead } from '../console/components/ui';

type PhraseTone = 'assistant' | 'colleague' | 'group';

const PHRASE_TONE: Record<PhraseTone, { box: string; label: string; text: string }> = {
  assistant: { box: 'bg-brand-50', label: 'text-brand-700', text: 'text-brand-950' },
  colleague: { box: 'bg-emerald-50', label: 'text-emerald-700', text: 'text-emerald-950' },
  group: { box: 'bg-slate-100', label: 'text-slate-600', text: 'text-ink' },
};

/** Пример фразы — крупно, видно с расстояния вытянутой руки, не мелким шрифтом инструкции. */
function Phrase({ tone, result, children }: { tone: PhraseTone; result: string; children: ReactNode }) {
  const t = PHRASE_TONE[tone];
  return (
    <div className={`rounded-lg ${t.box} p-4`}>
      <p className={`mb-1 text-[11px] font-semibold tracking-[0.06em] uppercase ${t.label}`}>
        Скажите вслух
      </p>
      <p className={`text-[19px] leading-snug font-bold ${t.text}`}>«{children}»</p>
      <p className="mt-2 text-[13.5px] leading-relaxed text-slate-600">{result}</p>
    </div>
  );
}

function Block({ icon: Icon, title, children }: { icon: LucideIcon; title: string; children: ReactNode }) {
  return (
    <Card className="p-5 sm:p-6">
      <div className="mb-3 flex items-center gap-2.5">
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-slate-100 text-slate-600">
          <Icon size={16} />
        </span>
        <h3 className="text-[16px] font-semibold text-ink sm:text-[17px]">{title}</h3>
      </div>
      <div className="space-y-3">{children}</div>
    </Card>
  );
}

/** Прямой ответ на вопрос, который обязан быть закрыт явно — крупнее обычного текста. */
function KeyAnswer({ children }: { children: ReactNode }) {
  return <p className="text-[15px] leading-relaxed font-semibold text-ink">{children}</p>;
}

function Warning({ children }: { children: ReactNode }) {
  return (
    <div className="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 p-3.5">
      <AlertTriangle size={16} className="mt-0.5 shrink-0 text-amber-600" />
      <p className="text-[13px] leading-relaxed text-amber-900">{children}</p>
    </div>
  );
}

export default function HelpView() {
  return (
    <>
      <PageHead
        title="Как это работает"
        subtitle="Держите кнопку — говорите. Что сказать вслух, чтобы услышал нужный человек, а не весь зал."
      />

      <div className="mb-8 grid gap-3 sm:grid-cols-3">
        <Phrase tone="assistant" result="Спросить про меню — вслух, в любой момент.">
          Онви, что в составе лагмана
        </Phrase>
        <Phrase tone="colleague" result="Позвать одного человека — услышит только он.">
          Азиз, подойди к шестому столу
        </Phrase>
        <Phrase tone="group" result="Сказать всей кухне сразу.">
          Кухня, два лагмана без острого
        </Phrase>
      </div>

      {/* --- Ассистент ------------------------------------------------- */}
      <SectionHead
        eyebrow="Ассистент"
        title="Спросить помощника"
        hint="Скажите «Онви» — ответит голосом, только по меню заведения, ничего не придумывая."
      />
      <div className="mb-8 space-y-3">
        <Block icon={Sparkles} title="Как задать вопрос">
          <Phrase tone="assistant" result="Ответит голосом на вашем языке — по данным меню, ничего лишнего.">
            Онви, что в составе лагмана
          </Phrase>
          <p className="text-[13.5px] leading-relaxed text-slate-600">
            Распознавание слышит «Онви» по-разному — подойдёт и «Анви», и «Энви». Важно только сказать
            его первым словом фразы.
          </p>
        </Block>

        <Block icon={UtensilsCrossed} title="Про аллергены спрашивайте всегда">
          <Phrase tone="assistant" result="Ответит по техкарте блюда — если данные в неё внесены.">
            Онви, есть в лагмане орехи
          </Phrase>
          <Warning>
            Если данных по блюду нет, Онви прямо скажет: «в карточке этого нет, уточни на кухне». Это
            не значит, что аллергенов нет — значит, что карточка не заполнена. Уточните на кухне, прежде
            чем отвечать гостю.
          </Warning>
        </Block>

        <Block icon={CircleHelp} title="Чтобы вопрос ушёл помощнику, а не в рацию">
          <KeyAnswer>Скажите «Онви» в начале фразы — вопрос уйдёт помощнику, что бы ни было выбрано на экране в «Кому».</KeyAnswer>
          <p className="text-[13.5px] leading-relaxed text-slate-600">
            Второй способ — оставить на экране «Кому: Ассистенту» (так стоит по умолчанию, когда вы
            открываете рацию).
          </p>
          <Warning>
            Если на экране осталось выбрано «Кухне» или чьё-то имя — например, вы только что передали
            заказ, — а следующий вопрос задан без «Онви» в начале, Onvy решит, что фраза для кухни, и
            отправит её как есть, без ответа. Привычка: если спрашиваете про меню, начинайте с «Онви».
          </Warning>
        </Block>
      </div>

      {/* --- Рация ------------------------------------------------- */}
      <SectionHead
        eyebrow="Рация"
        title="Позвать людей"
        hint="Голосом или пальцем — выбирайте, что удобнее с подносом в руках."
      />
      <div className="mb-8 space-y-3">
        <Block icon={Lock} title="Одному человеку — чтобы услышал только он">
          <KeyAnswer>Назовите его по имени в начале фразы — услышит только он, даже управляющий не получит копию.</KeyAnswer>
          <Phrase tone="colleague" result="Услышит только Азиз. Управляющему реплика не приходит.">
            Азиз, подойди к шестому столу
          </Phrase>
          <p className="text-[13.5px] leading-relaxed text-slate-600">
            Так же работает через глагол: «скажи Азизу принести чай», «спроси у Азиза, есть ли
            баранина». Обращайтесь по кличке, которой зовут на смене, — распознавание справляется с ней
            увереннее, чем с полным именем, и падежи не мешают: «Азизу», «Азиза» тоже сработают.
          </p>
          <p className="text-[13.5px] leading-relaxed text-slate-600">
            Неудобно говорить вслух — нажмите «Кому» на экране, найдите имя в списке и держите кнопку.
            Приватность та же.
          </p>
        </Block>

        <Block icon={Users} title="Всему отделу — вслух">
          <Phrase tone="group" result="Услышит вся кухня, кто сейчас на смене, и управляющий — он слышит рацию всегда.">
            Кухня, два лагмана без острого
          </Phrase>
          <p className="text-[13.5px] leading-relaxed text-slate-600">
            Так же работают «бар», «зал» и «все». Слово-адресат должно стоять первым в фразе или сразу
            за «скажи», «передай», «спроси».
          </p>
        </Block>

        <Block icon={AlertTriangle} title="Середина фразы — не обращение">
          <p className="text-[13.5px] leading-relaxed text-slate-600">
            Отдел или имя, упомянутые не в начале фразы, обращением не считаются — иначе половина
            вопросов про меню улетала бы коллегам.
          </p>
          <div className="rounded-lg bg-slate-100 p-4">
            <p className="text-[16px] leading-snug font-semibold text-slate-500 line-through decoration-slate-400">
              «я сказал кухне, что стол ждёт»
            </p>
            <p className="mt-2 text-[13.5px] leading-relaxed text-slate-600">
              «кухня» здесь не первое слово — Onvy не отправит это на кухню. Начните с «Кухня, …» или
              «скажи кухне …».
            </p>
          </div>
        </Block>
      </div>

      {/* --- Приватность и данные ------------------------------------------------- */}
      <SectionHead
        eyebrow="Приватность"
        title="Кто услышит и что происходит с голосом"
        hint="Разные национальности в смене и личные разговоры — предусмотрены с самого начала."
      />
      <div className="mb-8 space-y-3">
        <Block icon={WifiOff} title="Доходит только до тех, кто сейчас на связи">
          <p className="text-[13.5px] leading-relaxed text-slate-600">
            Реплика уходит тем, кто сейчас на смене и держит приложение открытым. Если человек ещё не
            вышел на смену или закрыл приложение, реплика его не дождётся и не догонит через час —
            Onvy честно ответит «Никого нет на связи — не передал.»
          </p>
        </Block>

        <Block icon={ShieldCheck} title="Разные языки — не проблема">
          <p className="text-[13.5px] leading-relaxed text-slate-600">
            Официант говорит по-узбекски — повар-таджик услышит перевод на своём языке, и наоборот.
            Перевод и озвучка идут автоматически. Если перевод не сработал, коллега всё равно услышит
            оригинал с пометкой «перевод не сработал» — тишины не будет никогда.
          </p>
        </Block>

        <Block icon={EyeOff} title="Разговоры с гостями остаются вашими">
          <KeyAnswer>
            Всё, что вы говорите гостю за столом, Onvy выбрасывает. Не сохраняет, не разбирает и не
            показывает управляющему.
          </KeyAnswer>
          <p className="text-[13.5px] leading-relaxed text-slate-600">
            В режиме «Онви слушает» микрофон открыт всю смену — но обрабатывается только то, что
            начинается с «Онви». Фраза без обращения отбрасывается сразу: она никуда не записывается
            и не возвращается даже вам на экран.
          </p>
          <p className="text-[13.5px] leading-relaxed text-slate-600">
            Onvy хранит только текст рабочих реплик — тех, что вы сказали ассистенту или коллегам.
            Звук не хранится нигде и никогда. Никого не узнают по голосу: продукт не сравнивает
            голоса и не строит на них профилей.
          </p>
        </Block>
      </div>

      {/* --- Короткая расшифровка пометок на экране ------------------------------------------------- */}
      <SectionHead title="Короткие пометки на экране" hint="Если Onvy написал одно из этого — вот что оно значит." />
      <Card>
        <ul className="divide-y divide-slate-100">
          {[
            {
              text: 'Не расслышал',
              meaning: 'Распознавание не справилось с шумом. Повторите ближе к микрофону.',
            },
            {
              text: 'Ассистент недоступен, связь работает',
              meaning: 'Рация работает как обычно, ответ по меню сейчас недоступен. Спросите ещё раз через минуту.',
            },
            {
              text: 'Голос не пришёл — читайте текст',
              meaning: 'Ответ есть и верен, просто без озвучки — прочитайте его на экране.',
            },
            {
              text: 'Никого нет на связи — не передал',
              meaning: 'Тот, кому вы говорили, сейчас не на смене или закрыл приложение. Найдите человека лично.',
            },
          ].map((row) => (
            <li key={row.text} className="flex flex-wrap items-baseline gap-x-4 gap-y-1 px-4 py-3.5 sm:flex-nowrap">
              <span className="w-full shrink-0 text-[14px] font-semibold text-ink sm:w-72">
                «{row.text}»
              </span>
              <span className="text-[13.5px] leading-relaxed text-slate-600">{row.meaning}</span>
            </li>
          ))}
        </ul>
      </Card>
    </>
  );
}
