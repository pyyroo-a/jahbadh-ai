import { useEffect, useMemo, useReducer, useState } from "react";
import { ApiError, addCombo, demoFeed, getConfig, ingestUrl, liveUrl, replayUrl, skipLive, spotlight, startLive } from "./api/client";
import { openStream } from "./api/stream";
import type { DeskConfig, FeedItem, Language, Persona, PlayerFollow } from "./api/types";
import ControlBar, { type Source } from "./components/ControlBar";
import DeskFeed, { Moment } from "./components/DeskFeed";
import EventStream from "./components/EventStream";
import FollowPanel from "./components/FollowPanel";
import HighlightsStrip from "./components/HighlightsStrip";
import AnalystLayout from "./components/layouts/AnalystLayout";
import FanLayout from "./components/layouts/FanLayout";
import PlayerWatchLayout from "./components/layouts/PlayerWatchLayout";
import MetricFocus from "./components/MetricFocus";
import ModeBar from "./components/ModeBar";
import OverlayPreview, { LowerThirds } from "./components/OverlayPreview";
import RecapPanel from "./components/RecapPanel";
import TacticalView from "./components/TacticalView";
import TopBar from "./components/TopBar";
import { comboWaiting, initialDesk, reduce, replaySkip } from "./state/desk";
import type { Selection } from "./state/evidence";
import { highlights } from "./state/highlights";
import { COMBO_NOTICES, WATCH_LABELS } from "./state/labels";
import { layoutFor } from "./state/layout";
import { activeCues, tickingClock } from "./state/overlay";
import { claimTags, inFocus, rankClaims, type Mode } from "./state/personal";
import { followFirst } from "./state/players";
import { usePhone } from "./state/usePhone";

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
  const [overlayOn, setOverlayOn] = useState(false);
  const [heardAt, setHeardAt] = useState(0);              // real time of the last stream message
  const phone = usePhone();

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
    const url = source.kind === "replay" ? replayUrl(source.matchId, source.speed, source.fromT)
      : source.kind === "ingest" ? ingestUrl(source.runId) : liveUrl(source.runId);
    return openStream(url, (m) => { setProblem(null); setHeardAt(performance.now()); dispatch(m); },
      () => setProblem("Reconnecting to the desk..."),
      () => setProblem(source.kind !== "replay"
        ? "This live match is no longer running. Back to the replay is one click away."
        : "The replay stream has stopped. Reload the page to start it again."));
  }, [source]);

  const liveRunId = source?.kind === "live" ? source.runId : null;
  const runId = source && source.kind !== "replay" ? source.runId : null;      // live or ingest
  const runKind = source?.kind === "ingest" ? "ingest" : "live";
  const { info, state, events } = desk;
  const clock = desk.clock;

  // The overlay keeps time between messages like a broadcast clock, so a cue leaves the screen on time.
  const [now, setNow] = useState(0);
  useEffect(() => {
    if (!overlayOn) return;
    const id = setInterval(() => setNow(performance.now()), 250);
    return () => clearInterval(id);
  }, [overlayOn]);
  const onAir = tickingClock(clock, heardAt, Math.max(now, heardAt), info?.speed ?? 6, !desk.ended);
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
    if (p !== persona) setSelection(null);       // a new persona starts from the overview
    setPersona(p);
    setLanguage(l);
    const key = `${p}|${l}`;
    if (!liveRunId || desk.info?.mode !== "live" || key === "pundit|en" || requested.has(key)) return;
    addCombo(liveRunId, p, l).then(({ accepted, reason }) => {
      if (accepted) setRequested((s) => new Set(s).add(key));
      else setNotice(COMBO_NOTICES[reason ?? "limit"]);
    }).catch(() => setNotice(COMBO_NOTICES.failed));
  }
  const waiting = (item: FeedItem) => comboWaiting(requested, item, persona, language, desk.ended !== null);

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
    onWatchFeed: () => demoFeed().then((r) => {
      setLiveNotice(r.joined ? "You've joined the outside feed that's already playing." : null);
      switchTo({ kind: "ingest", runId: r.run_id });
    }).catch(say),
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

  const layout = layoutFor(persona);
  const calm = layout === "fan", detail = layout === "analyst";
  const feedProps = { desk, persona, language, selection, onSelect: setSelection, waiting, mode, choices, calm, detail };
  const tacticalView = info ? (
          <TacticalView info={info} state={state} selected={selected} eventsById={desk.eventsById} mode={mode}
            heatmap={mode.kind === "player" ? follow?.heatmap ?? null : null}
            overlayControls={<OverlayPreview on={overlayOn} onToggle={() => setOverlayOn(!overlayOn)}
              feedUrl={liveRunId ? `/api/live/${liveRunId}/overlay` : source?.kind === "ingest" ? null : `/api/replay/${info.match_id}/overlay`} />}
            onOverview={() => setSelection(null)} calm={calm}
            onPitch={overlayOn && <LowerThirds cues={activeCues(desk.cues, onAir)} language={language} info={info} />}>
            {mode.kind === "player" && (
              <FollowPanel key={mode.playerId} info={info} playerId={mode.playerId} clock={clock} runId={runId} runKind={runKind}
                items={desk.items} persona={persona} language={language} onFollow={setFollow}
                onSpent={() => getConfig().then((c) => setLiveRemaining(c.live_remaining)).catch(() => undefined)} />
            )}
            {choice && (
              <MetricFocus info={info} choice={choice} states={desk.states} pinned={pinned} persona={persona}
                language={language} onPick={(momentId, claimId) => setSelection({ momentId, claimId })} />
            )}
          </TacticalView>
        ) : <section className="column"><h2>Tactical view</h2>Waiting for kick-off</section>;

  return (
    <div className="desk">
      <TopBar info={info} state={state} minute={minute} persona={persona} language={language}
        onPersona={(p) => pick(p, language)} onLanguage={(l) => pick(persona, l)} />
      {source && (
        <ControlBar source={source} info={info} liveMode={config?.live_mode ?? false} liveRemaining={liveRemaining}
          ingestOn={config?.ingest?.on ?? false}
          nextMoment={info && source.kind === "replay" ? replaySkip(info, clock, source.seen)?.seen ?? null : null} thinking={desk.thinking.length} notice={liveNotice}
          {...controls}>
          <RecapPanel items={desk.items} mode={mode} persona={persona} language={language}
            onPick={(momentId, claimId) => setSelection({ momentId, claimId })} />
        </ControlBar>
      )}
      {info && <ModeBar info={info} choices={choices} mode={mode} onMode={(m) => { setMode(m); setSelection(null); }} />}
      <HighlightsStrip strip={strip} onPick={pickMoment} />
      {problem && !desk.ended && <div className="notice">{problem}</div>}
      {phone && layout === "fan" ? (
        <FanLayout desk={desk} language={language} tactical={tacticalView} tacticalOpen={selection !== null}
          renderItem={(item) => <Moment item={item} {...feedProps} />} />
      ) : layout === "analyst" && info ? (
        <AnalystLayout desk={desk} info={info} phone={phone} tactical={tacticalView} tacticalOpen={selection !== null}
          feed={<DeskFeed {...feedProps} notice={notice} />} />
      ) : layout === "watch" && info ? (
        <PlayerWatchLayout desk={desk} info={info} phone={phone} clock={clock} runId={runId} runKind={runKind}
          followed={mode.kind === "player" ? mode.playerId : null}
          onFollow={(playerId) => { setMode({ kind: "player", playerId }); setSelection(null); }}
          tactical={tacticalView}
          feed={<DeskFeed {...feedProps} notice={notice} title={mode.kind === "player" ? WATCH_LABELS.feed : undefined}
            reorder={mode.kind === "player" ? (items) => followFirst(items, (item) =>
              rankClaims(item, mode, info, desk.eventsById, choices).some((r) => r.focus)) : undefined} />} />
      ) : (
        <main className="columns">
          <EventStream events={events} language={language} highlighted={highlighted}
            scrollKey={selection ? `${selection.momentId}|${selection.claimId}` : null} />
          {tacticalView}
          <DeskFeed {...feedProps} notice={notice} />
        </main>
      )}
    </div>
  );
}
