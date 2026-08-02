// store.js — 統計(/api/v2/stats)のキャッシュ
import { api } from "./api.js";

let statsPromise = null;

export function getStats(force = false) {
  if (!statsPromise || force) {
    statsPromise = api("/api/v2/stats");
    statsPromise.catch(() => {
      statsPromise = null; // 失敗はキャッシュしない
    });
  }
  return statsPromise;
}
