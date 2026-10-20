// The desk's JSON endpoints. Errors carry the server's friendly detail line, ready to show as it is.

import type { DeskConfig, Language, Persona, PlayerFollow, PlayerRow } from "./types";

export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.status = status;
    this.detail = detail;
  }
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, init);
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    const detail = typeof body?.detail === "string" ? body.detail : `The desk answered ${res.status}.`;
    throw new ApiError(res.status, detail);
  }
  return body as T;
}

const post = <T>(path: string, json?: unknown) => call<T>(path, {
  method: "POST",
  headers: json === undefined ? undefined : { "Content-Type": "application/json" },
  body: json === undefined ? undefined : JSON.stringify(json),
});

export const getConfig = () => call<DeskConfig>("/api/config");

export const startLive = () => post<{ run_id: string; joined: boolean; remaining: number }>("/api/live");

export const skipLive = (runId: string) => post<{ clock: number | null }>(`/api/live/${runId}/skip`);

export const spotlight = (runId: string, playerId: string) =>
  post<{ moment_id: string }>(`/api/live/${runId}/spotlight`, { player_id: playerId });

export const addCombo = (runId: string, persona: Persona, language: Language) =>
  post<{ accepted: boolean; reason: "finished" | "limit" | null }>(`/api/live/${runId}/combo`, { persona, language });

export const replayUrl = (matchId: string, speed: number, fromT = 0) =>
  `/api/replay/${matchId}/stream?speed=${speed}&from_t=${fromT}`;

export const liveUrl = (runId: string) => `/api/live/${runId}/stream`;

export type RunKind = "live" | "ingest";

export const ingestUrl = (runId: string) => `/api/ingest/${runId}/stream`;

/** The "Watch an outside feed" button: the demo feeder plays a match into the ingest API. */
export const demoFeed = () => post<{ run_id: string; joined: boolean }>("/api/ingest/demo");

/** One player up to t: from the showcase in replay, or clamped to the clock in live mode. */
export const getFollow = (matchId: string, playerId: string, t: number, runId: string | null = null, kind: RunKind = "live") =>
  call<PlayerFollow>(runId
    ? `/api/${kind}/${runId}/follow/${playerId}?t=${t}`
    : `/api/replay/${matchId}/follow/${playerId}?t=${t}`);

export const getPlayers = (matchId: string, t: number, runId: string | null = null, kind: RunKind = "live") =>
  call<PlayerRow[]>(runId ? `/api/${kind}/${runId}/players?t=${t}` : `/api/replay/${matchId}/players?t=${t}`);
