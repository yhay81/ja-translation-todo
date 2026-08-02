// components/status-badge.js — status を色+ラベルで表現するバッジ
import { STATUS_LABELS } from "../labels.js";

class StatusBadge extends HTMLElement {
  static observedAttributes = ["status"];

  connectedCallback() {
    this.render();
  }

  attributeChangedCallback() {
    this.render();
  }

  render() {
    const status = this.getAttribute("status") || "";
    this.className = `badge status-${status}`;
    this.textContent = STATUS_LABELS[status] || status || "不明";
  }
}

customElements.define("tt-status-badge", StatusBadge);
