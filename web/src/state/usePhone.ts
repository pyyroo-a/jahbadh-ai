// True on a phone-width screen, kept in step with the window as it resizes.

import { useSyncExternalStore } from "react";
import { PHONE_QUERY } from "./layout";

function subscribe(onChange: () => void) {
  const query = window.matchMedia(PHONE_QUERY);
  query.addEventListener("change", onChange);
  return () => query.removeEventListener("change", onChange);
}

export function usePhone(): boolean {
  return useSyncExternalStore(subscribe, () => window.matchMedia(PHONE_QUERY).matches, () => false);
}
