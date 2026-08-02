// pages/not-found.js — 404ページ
export async function renderNotFound(outlet) {
  document.title = "ページが見つかりません — ja-translation-todo";
  outlet.innerHTML = `
    <div class="notfound-page">
      <p class="code">404</p>
      <h1>ページが見つかりません</h1>
      <p>URLが正しいかご確認ください。</p>
      <p><a class="button primary" href="/">タスク一覧へ戻る</a></p>
    </div>`;
}
