import { useEffect, useRef, useState } from "react";
import type { EventLine, Language } from "../api/types";
import { visibleEvents } from "../state/events";

type Props = { events: EventLine[]; language: Language; highlighted: Set<number> };

export default function EventStream({ events, language, highlighted }: Props) {
  const [mode, setMode] = useState<"key" | "all">("key");
  const list = useRef<HTMLOListElement>(null);
  const shown = visibleEvents(events, mode, highlighted);

  useEffect(() => {       // bring the selected claim's evidence into view
    if (highlighted.size) list.current?.querySelector(".event.lit")?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [highlighted]);

  return (
    <section className="column events">
      <div className="column-head">
        <h2>Event stream</h2>
        <div className="pills small" role="group" aria-label="Which events">
          <button className={mode === "key" ? "pill on" : "pill"} onClick={() => setMode("key")}>Key events</button>
          <button className={mode === "all" ? "pill on" : "pill"} onClick={() => setMode("all")}>All events</button>
        </div>
      </div>
      <ol className="event-list" ref={list}>
        {shown.map((e) => (
          <li key={e.id} className={highlighted.has(e.id) ? "event lit" : "event"}>
            <span className="event-minute">{e.minute}'</span>
            <span dir={language === "ar" ? "rtl" : "ltr"}>{e.lines[language]}</span>
          </li>
        ))}
      </ol>
    </section>
  );
}
