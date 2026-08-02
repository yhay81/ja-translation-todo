// components/automation-meter.js — automation.level を段階メータ(●●○○○)で表示
import { AUTOMATION_LABELS, AUTOMATION_ORDER, esc } from "../labels.js";

class AutomationMeter extends HTMLElement {
  static observedAttributes = ["level"];

  connectedCallback() {
    this.render();
  }

  attributeChangedCallback() {
    this.render();
  }

  render() {
    const level = this.getAttribute("level") || "";
    const label = AUTOMATION_LABELS[level] || level || "不明";
    this.setAttribute("title", `自動化レベル: ${label}`);

    if (level === "blocked") {
      this.innerHTML = `<span class="meter-blocked" aria-hidden="true">⊘</span><span>${esc(label)}</span>`;
      return;
    }

    const steps = AUTOMATION_ORDER.indexOf(level) + 1;
    const total = AUTOMATION_ORDER.length;
    if (steps <= 0) {
      this.innerHTML = `<span>${esc(label)}</span>`;
      return;
    }
    const dots =
      "<span>●</span>".repeat(steps) + '<span class="off">○</span>'.repeat(total - steps);
    this.innerHTML =
      `<span class="meter-dots" aria-hidden="true">${dots}</span>` +
      `<span class="sr-only">自動化レベル ${steps}/${total}:</span>` +
      `<span>${esc(label)}</span>`;
  }
}

customElements.define("tt-automation-meter", AutomationMeter);
