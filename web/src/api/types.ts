// The desk's stream protocol, mirroring the Python models field for field (snake_case, as they come over the
// wire): jahbadh.schemas, jahbadh.agents.contracts, jahbadh.api.stream, jahbadh.api.overlay and
// jahbadh.api.personal. If a Python model changes, this file changes with it.

export type Persona = "pundit" | "casual" | "fantasy";
export type Language = "en" | "ar" | "es";
export type Layer = "deterministic" | "semantic" | "persona" | "localization";
export type Role = "GK" | "CB" | "FB" | "DM" | "CM" | "AM" | "W" | "ST";
export type EventType =
  | "KICKOFF" | "PASS" | "CARRY" | "SHOT" | "GOAL" | "TACKLE" | "INTERCEPTION" | "PRESSURE" | "FOUL" | "CARD"
  | "SUBSTITUTION" | "FORMATION_CHANGE" | "TACTIC_CHANGE" | "PERIOD_END";
export type MomentKind =
  | "goal" | "big_chance" | "card" | "substitution" | "formation_change" | "tactic_change" | "momentum_swing"
  | "check_in" | "full_time" | "spotlight" | "team_recap";

export interface Player {
  id: string;
  team_id: string;
  name: string;
  shirt: number;
  role: Role;
  starter: boolean;
}

export interface TeamTactics {
  press_height: number;
  width: number;
  tempo: number;
  directness: number;
}

export interface Team {
  id: string;
  name: string;
  formation: string;
  tactics: TeamTactics;
  players: Player[];
}

export interface Metric {
  id: string;
  name: string;
  subject: string;
  window: [number, number];
  value: number | null;
  unit: string;
  evidence_event_ids: number[];
  evidence_frames: [number, number] | null;
  data: Record<string, unknown>;
  note: string | null;
}

export interface Moment {
  id: string;
  kind: MomentKind;
  t: number;
  team_id: string | null;
  player_id: string | null;
  event_ids: number[];
  label: string;
}

export interface Figure {
  metric_id: string;
  field: string;
  written: string;
}

export interface Claim {
  id: string;
  text: string;
  metric_ids: string[];
  event_ids: number[];
  figures: Figure[];
}

export interface RenderedClaim {
  claim_id: string;
  persona: Persona;
  language: Language;
  text: string;
  note: string | null;
}

export interface Rejection {
  claim_id: string;
  text: string;
  layer: Layer;
  reasons: string[];
  attempt: number;
  persona: Persona | null;      // null: the writer's draft, rejected by the Referee
  language: Language | null;
}

export interface FeedItem {
  moment: Moment;
  claims: Claim[];
  renders: RenderedClaim[];
  rejections: Rejection[];
  metrics: Metric[];
  stats: Record<string, number>;
  latency_s: number;
}

export interface MomentFailure {
  moment_id: string;
  error: string;
}

export interface MatchInfo {
  match_id: string;
  mode: "replay" | "live" | "ingest";
  home: Team;
  away: Team;
  speed: number;
  precomputed: boolean;
  model: string | null;
  created: string | null;
  moment_times: number[];
}

export interface EventLine {
  id: number;
  t: number;
  minute: number;
  type: EventType;
  team_id: string;
  player_id: string | null;
  related_player_id: string | null;
  x: number;
  y: number;
  end_x: number | null;
  end_y: number | null;
  outcome: boolean | null;
  xg: number | null;
  speed_kmh: number | null;          // synthetic ball speed, on passes and shots only
  lines: Record<Language, string>;
}

export interface MatchState {
  t: number;
  minute: number;
  score: Record<string, number>;
  xg: Record<string, number>;
  momentum: number | null;
  field_tilt: number | null;
  ppda: Record<string, number | null>;
  shape: Record<string, Metric>;
  formations: Record<string, string>;
  rhythm: Metric | null;
  pass_difficulty: Record<string, number | null>;
  pass_speed: Record<string, number | null>;   // each team's mean synthetic pass speed, km/h
  shots: Record<string, number>;               // each team's shots so far
}

export interface RendersUpdate {
  moment_id: string;
  renders: RenderedClaim[];
  rejections: Rejection[];
}

/** One of the desk's steps finished for a moment, at match second t (live and ingest). Persona and Localize
 *  are part of publish. */
export type DeskStep = "analyst" | "tactical" | "writer" | "referee" | "rewrite" | "recheck" | "publish";

export interface StepUpdate {
  moment_id: string;
  step: DeskStep;
  t: number;
}

/** From match second t the clock runs at `speed`; `holding` names the key moments slowing it, earliest first. */
export interface PaceUpdate {
  t: number;
  speed: number;
  holding: string[];
}

export interface StreamEnd {
  reason: "full_time" | "cancelled";
}

export type CueType =
  | "goal" | "card" | "substitution" | "formation_change" | "tactic_change" | "shot" | "sprint_record"
  | "distance_milestone" | "rhythm" | "claim";

export interface OverlayCue {
  id: string;
  match_time: number;
  minute: number;
  type: CueType;
  team_id: string | null;
  player_id: string | null;
  value: number | null;
  unit: string | null;
  text: Record<Language, string>;
  duration_s: number;
  event_ids: number[];
  metric_ids: string[];
  source: "event" | "metric" | "claim";
  synthetic: boolean;
  precomputed: boolean;
}

export interface PlayerFollow {
  player_id: string;
  t: number;
  on_pitch: boolean;
  impact: Metric;
  heatmap: Metric;
  physical: Metric;
  passing: Metric;
  pass_speed: Metric;              // synthetic, from the simulator
  event_ids: number[];
}

/** One line of Player watch: what a player has done up to t. Pass speeds are synthetic. */
export interface PlayerRow {
  player_id: string;
  name: string;
  team_id: string;
  shirt: number;
  role: string;
  on_pitch: boolean;
  minutes: number;
  xgi: number;
  xg: number;
  goals: number;
  assists: number;
  shots: number;
  ball_wins: number;
  yellow_cards: number;
  red_cards: number;
  pass_speed_avg: number | null;
  pass_speed_max: number | null;
}

export interface MetricChoice {
  key: string;
  label: string;
  state_field: string;
  metric_names: string[];
}

export interface ShowcaseSummary {
  match_id: string;
  home: string;
  away: string;
  score: Record<string, number>;
  model: string;
  created: string;
}

export interface DeskConfig {
  live_mode: boolean;
  live_remaining: number;
  showcases: ShowcaseSummary[];
  metric_choices: MetricChoice[];
  ingest: { on: boolean; run_id: string | null };
}

export type StreamMessage = { id: number } & (
  | { kind: "match"; data: MatchInfo }
  | { kind: "event"; data: EventLine }
  | { kind: "state"; data: MatchState }
  | { kind: "thinking"; data: Moment }
  | { kind: "feed"; data: FeedItem }
  | { kind: "failure"; data: MomentFailure }
  | { kind: "renders"; data: RendersUpdate }
  | { kind: "cue"; data: OverlayCue }
  | { kind: "end"; data: StreamEnd }
  | { kind: "step"; data: StepUpdate }
  | { kind: "pace"; data: PaceUpdate }
);

export type StreamKind = StreamMessage["kind"];
export const STREAM_KINDS: StreamKind[] = ["match", "event", "state", "thinking", "feed", "failure", "renders", "cue", "end", "step", "pace"];
