import { useEffect, useReducer, useState } from "react";
import { getConfig, replayUrl } from "./api/client";
import { openStream } from "./api/stream";
import { initialDesk, reduce } from "./state/desk";

// The shell: follow the first showcase's replay at 6x. Tasks 10 to 12 fill the three columns in.
export default function App() {
  const [desk, dispatch] = useReducer(reduce, initialDesk);
  const [problem, setProblem] = useState<string | null>(null);

  useEffect(() => {
    let close = () => {};
    let gone = false;
    getConfig()
      .then((cfg) => {
        const show = cfg.showcases[0];
        if (gone) return;
        if (!show) return setProblem("No showcase match is loaded on this server.");
        close = openStream(replayUrl(show.match_id, 6), dispatch, () => setProblem("Reconnecting to the desk..."));
      })
      .catch(() => setProblem("The desk isn't answering. Is the API running?"));
    return () => { gone = true; close(); };
  }, []);

  const { info, state, events } = desk;
  const minute = events.length ? events[events.length - 1].minute : state?.minute ?? 1;
  const score = (id?: string) => (id && state?.score[id]) ?? 0;

  return (
    <div className="desk">
      <header className="topbar">
        <div className="brand"><img src="/jahbadh-icon.png" alt="" />Jahbadh</div>
        {info && (
          <div className="score">
            <span className="home">{info.home.name}</span>
            <strong>{score(info.home.id)} - {score(info.away.id)}</strong>
            <span className="away">{info.away.name}</span>
            <span className="minute">{minute}'</span>
          </div>
        )}
        {info && <span className="badge">{info.precomputed ? "Replay · precomputed by the real desk" : "Live"}</span>}
      </header>
      {problem && !desk.ended && <div className="notice">{problem}</div>}
      <main className="columns">
        <section className="column"><h2>Event stream</h2>{events.length} events</section>
        <section className="column"><h2>Tactical view</h2>{state ? `${state.minute}' state` : "Waiting for kick-off"}</section>
        <section className="column">
          <h2>Desk feed</h2>
          {desk.items.length} published, {desk.thinking.length} thinking, {desk.failures.length} failed
        </section>
      </main>
    </div>
  );
}
