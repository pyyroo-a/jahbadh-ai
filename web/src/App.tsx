import { useEffect, useMemo, useReducer, useState } from "react";
import { ApiError, addCombo, getConfig, liveUrl, replayUrl, skipLive, spotlight, startLive } from "./api/client";
import { openStream } from "./api/stream";
import type { DeskConfig, FeedItem, Language, Persona, PlayerFollow } from "./api/types";
import ControlBar, { type Source } from "./components/ControlBar";
import DeskFeed from "./components/DeskFeed";
import EventStream from "./components/EventStream";
import FollowPanel from "./components/FollowPanel";
import HighlightsStrip from "./components/HighlightsStrip";
import MetricFocus from "./components/MetricFocus";
import ModeBar from "./components/ModeBar";
import RecapPanel from "./components/RecapPanel";
import TacticalView from "./components/TacticalView";
import TopBar from "./components/TopBar";
import { hasCombo, initialDesk, reduce, replaySkip } from "./state/desk";
import type { Selection } from "./state/evidence";
import { highlights } from "./state/highlights";
import { claimTags, inFocus, type Mode } from "./state/personal";

export default function App() {
  const [desk, dispatch] = useReducer(reduce, initialDesk);
  const [config, setConfig] = useState<DeskConfig | null>(null);
  const [source, setSource] = useState<Source | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [persona, setPersona] = useState<Persona>("pundit");
  const [language, setLanguage] = useState<Language>("en");
  const [selection, setSelection] = useState<Selection>(null);
  const [mode, setMode] = useState<Mode>({ kind: "all" });
  const [follow, setFollow] = useState<PlayerFollow | null>(null);
  const [requested, setRequested] = useState<Set<string>>(new Set());
  const [notice, setNotice] = useState<string | null>(null);
  const [liveNotice, setLiveNotice] = useState<string | null>(null);
  const [liveRemaining, setLiveRemaining] = useState(0);

  useEffect(() => {
    getConfig()
      .then((cfg) => {
        setConfig(cfg);
        setLiveRemaining(cfg.live_remaining);
        const show = cfg.showcases[0];
        if (!show) return setProblem("No showcase match is loaded on this server.");
        setSource({ kind: "replay", matchId: show.match_id, speed: 6, fromT: 0, seen: 0 });
      })
      .catch(() => setProblem("The desk isn't answering. Is the API running?"));
  }, []);

  useEffect(() => {               // one stream at a time; a new source starts over from its match message
    if (!source) return;
    const url = source.kind === "replay" ? replayUrl(source.matchId, source.speed, source.fromT) : liveUrl(source.runId);
    return openStream(url, (m) => { setProblem(null); dispatch(m); }, () => setProblem("Reconnecting to the desk..."));
  }, [source]);

  const liveRunId = source?.kind === "live" ? source.runId : null;
  const { info, state, events } = desk;
  const clock = Math.max(events.at(-1)?.t ?? 0, state?.t ?? 0);
  const minute = events.length ? events[events.length - 1].minute : state?.minute ?? 1;
  const choices = useMemo(() => config?.metric_choices ?? [], [config]);

  function switchTo(next: Source) {
    setSource(next);
    setSelection(null);
    setRequested(new Set());
    setNotice(null);
  }

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

  const say = (e: unknown) => setLiveNotice(e instanceof ApiError ? e.detail : "The desk couldn't take that request.");
  const controls = {
    onSpeed: (speed: number) => source?.kind === "replay" && switchTo({ ...source, speed, fromT: clock, seen: clock }),
    onSkip: () => {
      if (source?.kind === "replay" && info) {
        const jump = replaySkip(info, clock, source.seen);
        if (jump) switchTo({ ...source, ...jump });
      } else if (liveRunId) {
        skipLive(liveRunId).then(({ clock: c }) => c === null && setLiveNotice("There's no moment left to skip to.")).catch(say);
      }
    },
    onRunLive: () => startLive().then((r) => {
      setLiveRemaining(r.remaining);
      setLiveNotice(r.joined ? "You've joined the live match that's already running." : null);
      switchTo({ kind: "live", runId: r.run_id });
    }).catch(say),
    onSpotlight: (playerId: string) => liveRunId && spotlight(liveRunId, playerId)
      .then(() => setLiveNotice("The desk is on it. The spotlight lands in the feed shortly."))
      .then(() => getConfig().then((c) => setLiveRemaining(c.live_remaining)))
      .catch(say),
    onBackToReplay: () => {
      const show = config?.showcases[0];
      if (show) switchTo({ kind: "replay", matchId: show.match_id, speed: 6, fromT: 0, seen: 0 });
      setLiveNotice(null);
    },
  };

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

  const strip = useMemo(() => highlights(desk.items, persona, language), [desk.items, persona, language]);
  const pickMoment = (momentId: string) => {
    const item = desk.items.find((i) => i.moment.id === momentId);
    if (item?.claims[0]) setSelection({ momentId, claimId: item.claims[0].id });
  };

  return (
    <div className="desk">
      <TopBar info={info} state={state} minute={minute} persona={persona} language={language}
        onPersona={(p) => pick(p, language)} onLanguage={(l) => pick(persona, l)} />
      {source && (
        <ControlBar source={source} info={info} liveMode={config?.live_mode ?? false} liveRemaining={liveRemaining}
          nextMoment={info && source.kind === "replay" ? replaySkip(info, clock, source.seen)?.seen ?? null : null} thinking={desk.thinking.length} notice={liveNotice}
          {...controls}>
          <RecapPanel items={desk.items} mode={mode} persona={persona} language={language}
            onPick={(momentId, claimId) => setSelection({ momentId, claimId })} />
        </ControlBar>
      )}
      {info && <ModeBar info={info} choices={choices} mode={mode} onMode={setMode} />}
      <HighlightsStrip strip={strip} onPick={pickMoment} />
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
