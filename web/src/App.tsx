import { useEffect, useMemo, useReducer, useState } from "react";
import { addCombo, getConfig, replayUrl } from "./api/client";
import { openStream } from "./api/stream";
import type { FeedItem, Language, Persona } from "./api/types";
import DeskFeed from "./components/DeskFeed";
import EventStream from "./components/EventStream";
import TopBar from "./components/TopBar";
import { hasCombo, initialDesk, reduce } from "./state/desk";
import type { Selection } from "./state/evidence";

const params = new URLSearchParams(location.search);       // ?speed=20&from=3600 until the control bar (Task 12)
const SPEED = Number(params.get("speed")) || 6;
const FROM_T = Number(params.get("from")) || 0;

export default function App() {
  const [desk, dispatch] = useReducer(reduce, initialDesk);
  const [problem, setProblem] = useState<string | null>(null);
  const [persona, setPersona] = useState<Persona>("pundit");
  const [language, setLanguage] = useState<Language>("en");
  const [selection, setSelection] = useState<Selection>(null);
  const [liveRunId] = useState<string | null>(null);              // Task 12 starts live runs
  const [requested, setRequested] = useState<Set<string>>(new Set());
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    let close = () => {};
    let gone = false;
    getConfig()
      .then((cfg) => {
        const show = cfg.showcases[0];
        if (gone) return;
        if (!show) return setProblem("No showcase match is loaded on this server.");
        close = openStream(replayUrl(show.match_id, SPEED, FROM_T), (m) => { setProblem(null); dispatch(m); },
          () => setProblem("Reconnecting to the desk..."));
      })
      .catch(() => setProblem("The desk isn't answering. Is the API running?"));
    return () => { gone = true; close(); };
  }, []);

  // Live mode publishes the pundit in English; any other combo is rendered once someone asks for it.
  function pick(p: Persona, l: Language) {
    setPersona(p);
    setLanguage(l);
    const key = `${p}|${l}`;
    if (!liveRunId || desk.info?.mode !== "live" || key === "pundit|en" || requested.has(key)) return;
    addCombo(liveRunId, p, l).then(({ accepted }) => {
      if (accepted) setRequested((s) => new Set(s).add(key));
      else setNotice("This live match already has its two extra versions.");
    }).catch(() => setNotice("This live match already has its two extra versions."));
  }
  const waiting = (item: FeedItem) =>
    requested.has(`${persona}|${language}`) && item.claims.length > 0 && !hasCombo(item, persona, language);

  const highlighted = useMemo(() => {
    const item = desk.items.find((i) => i.moment.id === selection?.momentId);
    const claim = item?.claims.find((c) => c.id === selection?.claimId);
    return new Set(claim?.event_ids ?? []);
  }, [desk.items, selection]);

  const { info, state, events } = desk;
  const minute = events.length ? events[events.length - 1].minute : state?.minute ?? 1;

  return (
    <div className="desk">
      <TopBar info={info} state={state} minute={minute} persona={persona} language={language}
        onPersona={(p) => pick(p, language)} onLanguage={(l) => pick(persona, l)} />
      {problem && !desk.ended && <div className="notice">{problem}</div>}
      <main className="columns">
        <EventStream events={events} language={language} highlighted={highlighted} />
        <section className="column"><h2>Tactical view</h2>{state ? `${state.minute}' state` : "Waiting for kick-off"}</section>
        <DeskFeed desk={desk} persona={persona} language={language} selection={selection} onSelect={setSelection}
          waiting={waiting} notice={notice} />
      </main>
    </div>
  );
}
