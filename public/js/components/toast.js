// components/toast.js — 画面右下の通知トースト
let host = null;

function ensureHost() {
  if (host && host.isConnected) return host;
  host = document.createElement("div");
  host.className = "toast-host";
  host.setAttribute("aria-live", "polite");
  document.body.appendChild(host);
  return host;
}

// kind: "info" | "success" | "error"
export function toast(message, kind = "info") {
  const el = document.createElement("div");
  el.className = `toast toast-${kind}`;
  el.setAttribute("role", "status");
  el.textContent = message;
  ensureHost().appendChild(el);
  setTimeout(() => {
    el.classList.add("out");
    setTimeout(() => el.remove(), 350);
  }, 4200);
}
