// api.js — fetch ラッパ(problem+json 対応)とエラートースト
import { toast } from "./components/toast.js";

// 同一オリジンAPI呼び出し。エラー時は problem+json を解釈した Error を投げる。
export async function api(path, { method = "GET", body, headers = {} } = {}) {
  const options = { method, headers: { ...headers } };
  if (body !== undefined) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }

  let res;
  try {
    res = await fetch(path, options);
  } catch (cause) {
    const err = new Error("ネットワークエラーが発生しました");
    err.cause = cause;
    throw err;
  }

  let data = null;
  const contentType = res.headers.get("content-type") || "";
  if (contentType.includes("json")) {
    try {
      data = await res.json();
    } catch {
      data = null;
    }
  }

  if (!res.ok) {
    const message =
      (data && (data.detail || data.title)) || `リクエストに失敗しました (HTTP ${res.status})`;
    const err = new Error(message);
    err.status = res.status;
    err.problem = data;
    throw err;
  }
  return data;
}

// エラーをトーストで通知する共通ヘルパ
export function toastError(err) {
  toast(err?.message || "エラーが発生しました", "error");
}
