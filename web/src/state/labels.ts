// The words the desk shows for its switches and checks.

import type { Language, Persona, Rejection } from "../api/types";

export const PERSONAS: { key: Persona; label: string }[] = [
  { key: "pundit", label: "Studio pundit" }, { key: "casual", label: "Casual fan" }, { key: "fantasy", label: "Fantasy" },
];

export const LANGUAGES: { key: Language; label: string }[] = [
  { key: "en", label: "EN" }, { key: "ar", label: "AR" }, { key: "es", label: "ES" },
];

export const LAYER_LABELS: Record<Rejection["layer"], string> = {
  deterministic: "Number and ID check",
  semantic: "Referee judge",
  persona: "Persona re-check",
  localization: "Translation check",
};

export const NOTES: Record<string, string> = {
  "persona fallback": "Shown in the pundit's words",
  "english fallback": "Shown in English",
  "raw translation": "Machine translation",
};
