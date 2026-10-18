import { useEffect, useMemo, useReducer, useState } from "react";
import { addCombo, getConfig, replayUrl } from "./api/client";
import { openStream } from "./api/stream";
import type { DeskConfig, FeedItem, Language, Persona, PlayerFollow } from "./api/types";
import DeskFeed from "./components/DeskFeed";
import EventStream from "./components/EventStream";
import FollowPanel from "./components/FollowPanel";
import MetricFocus from "./components/MetricFocus";
import ModeBar from "./components/ModeBar";
import TacticalView from "./components/TacticalView";
import TopBar from "./components/TopBar";
import { hasCombo, initialDesk, reduce } from "./state/desk";
import type { Selection } from "./state/evidence";
import { claimTags, inFocus, type Mode } from "./state/personal";

const params = new URLSearchParams(location.search);       // ?speed=20&from=3600 until the control bar (Task 12)
const SPEED = Number(params.get("speed")) || 6;
const FROM_T = Number(params.get("from")) || 0;

export default function App() {
  const [desk, dispatch] = useReducer(reduce, initialDesk);
  const [config, setConfig] = useState<DeskConfig | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [persona, setPersona] = useState<Persona>("pundit");
  const [language, setLanguage] = useState<Language>("en");
  const [selection, setSelection] = useState<Selection>(null);
  const [mode, setMode] = useState<Mode>({ kind: "all" });
  const [follow, setFollow] = useState<PlayerFollow | null>(null);
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
        setConfig(cfg);
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

  const choices = useMemo(() => config?.metric_choices ?? [], [config]);
  const { info, state, events } = desk;
  const clock = Math.max(events.at(-1)?.t ?? 0, state?.t ?? 0);
  const minute = events.length ? events[events.length - 1].minute : state?.minute ?? 1;

  // Lit in the stream: the clicked claim's evidence, plus everything a followed player has done.
  const highlighted = useMemo(() => {
    const item = desk.items.find((i) => i.moment.id === selection?.momentId);
    const claim = item?.claims.find((c) => c.id === selection?.claimId);
    const followed = mode.kind === "player" ? follow?.event_ids ?? [] : [];
    return new Set([...(claim?.event_ids ?? []), ...followed]);
  }, [desk.items, selection, mode.kind, follow]);

  const selected = useMemo(() => {
    const item = desk.items.find((i) => i.moment.id === selection?.momentId);
    const claim = item?.claims.find((c) => c.id === selection?.claimId);
    return item && claim ? { item, claim } : null;
  }, [desk.items, selection]);

  const choice = mode.kind === "metric" ? choices.find((c) => c.key === mode.key) : undefined;
  const pinned = useMemo(() => !info || mode.kind !== "metric" ? [] : desk.items.flatMap((item) => item.claims
    .filter((c) => inFocus(claimTags(item, c, info, desk.eventsById), mode, choices))
    .map((c) => ({ item, claimId: c.id }))), [desk.items, desk.eventsById, info, mode, choices]);

  return (
    <div className="desk">
      <TopBar info={info} state={state} minute={minute} persona={persona} language={language}
        onPersona={(p) => pick(p, language)} onLanguage={(l) => pick(persona, l)} />
      {info && <ModeBar info={info} choices={choices} mode={mode} onMode={setMode} />}
      {problem && !desk.ended && <div className="notice">{problem}</div>}
      <main className="columns">
        <EventStream events={events} language={language} highlighted={highlighted}
          scrollKey={selection ? `${selection.momentId}|${selection.claimId}` : null} />
        {info ? (
          <TacticalView info={info} state={state} selected={selected} eventsById={desk.eventsById} mode={mode}
            heatmap={mode.kind === "player" ? follow?.heatmap ?? null : null}>
            {mode.kind === "player" && (
              <FollowPanel key={mode.playerId} info={info} playerId={mode.playerId} clock={clock} runId={liveRunId}
                items={desk.items} persona={persona} language={language} onFollow={setFollow} />
            )}
            {choice && (
              <MetricFocus info={info} choice={choice} states={desk.states} pinned={pinned} persona={persona}
                language={language} onPick={(momentId, claimId) => setSelection({ momentId, claimId })} />
            )}
          </TacticalView>
        ) : <section className="column"><h2>Tactical view</h2>Waiting for kick-off</section>}
        <DeskFeed desk={desk} persona={persona} language={language} selection={selection} onSelect={setSelection}
          waiting={waiting} notice={notice} mode={mode} choices={choices} />
      </main>
    </div>
  );
}
