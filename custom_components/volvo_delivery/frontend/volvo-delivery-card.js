const ENTITY_FIELDS = {
  status_entity: "status",
  delivery_entity: "delivery_estimate",
  changes_entity: "order_changes",
  last_checked_entity: "last_checked",
  last_changed_entity: "last_changed",
};

const LABELS = {
  status_entity: "Leveransstatus",
  delivery_entity: "Beräknad leverans",
  changes_entity: "Orderändringar",
  last_checked_entity: "Senaste lyckade kontroll",
  last_changed_entity: "Senaste leveransändring",
};

function isAvailable(entity) {
  return entity && !["unknown", "unavailable"].includes(entity.state);
}

function entityText(entity) {
  return isAvailable(entity)
    ? entity.attributes.full_text || entity.state
    : null;
}

function resolveEntities(hass, config) {
  const states = hass?.states || {};
  const status = states[config.status_entity];
  const trackingId = status?.attributes.delivery_tracking_id;
  return Object.fromEntries(
    Object.entries(ENTITY_FIELDS).map(([key, field]) => {
      const discovered = trackingId
        ? Object.keys(states).find(
            (id) =>
              states[id].attributes.delivery_tracking_id === trackingId &&
              states[id].attributes.delivery_field === field,
          )
        : undefined;
      const id = config[key] || discovered;
      return [key, { id, entity: states[id] }];
    }),
  );
}

function calendarDay(value) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value || "")) return null;
  const date = new Date(`${value}T00:00:00Z`);
  return Number.isNaN(date.getTime()) ||
    date.toISOString().slice(0, 10) !== value
    ? null
    : date;
}

function todayInZone(now, timeZone) {
  const parts = new Intl.DateTimeFormat("sv-SE", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(now);
  const part = (type) => parts.find((item) => item.type === type).value;
  return calendarDay(`${part("year")}-${part("month")}-${part("day")}`);
}

function forecastView(entity, day) {
  if (!isAvailable(entity)) return null;
  const { estimated_start: startText, estimated_end: endText } =
    entity.attributes;
  const start = calendarDay(startText);
  const end = calendarDay(endText);
  if (!start || !end || (end - start) / 86400000 !== 6) return null;
  const days = Math.round((start - day) / 86400000);
  const endDays = Math.round((end - day) / 86400000);
  const format = (date) =>
    new Intl.DateTimeFormat("sv-SE", {
      day: "numeric",
      month: "short",
      year: "numeric",
      timeZone: "UTC",
    }).format(date);
  return {
    days: Math.max(0, days),
    phase: days > 0 ? "upcoming" : endDays >= 0 ? "current" : "past",
    range: `${format(start)} – ${format(end)}`,
  };
}

function stageIndex(text) {
  const stages = [
    ["din bil är orderlagd.", "din bil är beställd."],
    [
      "din bil är byggd och klar att lämna fabriken.",
      "din bil är byggd och redo att lämna fabriken.",
    ],
    [
      "din bil är på väg till din volvohandlare.",
      "din bil är på väg till din återförsäljare.",
    ],
    ["grattis! din nya bil är levererad.", "din bil är levererad."],
  ];
  return stages.findIndex((values) =>
    values.includes((text || "").trim().toLowerCase()),
  );
}

function volvoUrl(value, image = false) {
  if (!value) return null;
  const hosts = image
    ? ["wizz.volvocars.com", "www.volvocars.com", "dam.fbinhouse.se"]
    : ["www.volvocars.com"];
  try {
    const url = new URL(value);
    if (
      url.protocol === "https:" &&
      hosts.includes(url.hostname) &&
      !url.username &&
      !url.password &&
      !url.port
    )
      return url.href;
  } catch {
    return null;
  }
  return null;
}

const STYLES = `
  :host { display: block; container-type: inline-size; }
  * { box-sizing: border-box; }
  ha-card { display: block; overflow: hidden; border-radius: 24px; background: var(--ha-card-background, var(--card-background-color, #fff)); color: var(--primary-text-color, #172c2d); border: 1px solid var(--divider-color, #e1e6e2); }
  button { font: inherit; }
  button:focus-visible, summary:focus-visible, a:focus-visible { outline: 3px solid #609e82; outline-offset: 4px; }
  [hidden] { display: none !important; }
  .hero { position: relative; overflow: hidden; padding: 28px 28px 0; color: #f7faf1; background: linear-gradient(135deg, #10282b, #214b49); }
  .topline { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
  .eyebrow { font-size: 10px; font-weight: 700; letter-spacing: .2em; text-transform: uppercase; }
  .model { border: 1px solid #ffffff3b; border-radius: 30px; padding: 6px 12px; font-size: 12px; letter-spacing: .08em; }
  h1 { font-family: Georgia, serif; font-size: clamp(29px, 8cqi, 42px); line-height: 1.15; font-weight: 400; margin: 24px 0 10px; letter-spacing: -.025em; max-width: 290px; }
  .subtitle { margin: 0; font-size: 12px; color: #bed4ce; line-height: 1.6; max-width: 330px; }
  .scene { display: block; width: calc(100% + 56px); height: 128px; margin: 8px -28px 0; }
  .vehicle-photo { max-width: 320px; margin: 16px auto 18px; border-radius: 12px; overflow: hidden; background: #f4f5f2; color: #233e3b; }
  .vehicle-photo img { display: block; width: 100%; aspect-ratio: 2 / 1; max-height: 144px; object-fit: contain; }
  .vehicle-photo figcaption { text-align: center; padding: 6px 12px 8px; font-size: 10px; color: #586d67; }
  .image-notice { font-size: 11px; line-height: 1.6; margin: 12px 0; color: #bed4ce; }
  .body { padding: 24px 28px; }
  .countdown { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
  .number { font-size: clamp(52px, 18cqi, 80px); font-weight: 300; line-height: 1; letter-spacing: -.075em; font-variant-numeric: tabular-nums; }
  .unit { font-size: 16px; font-weight: 400; letter-spacing: 0; margin-left: 9px; }
  .muted { color: var(--secondary-text-color, #617270); font-size: 12px; line-height: 1.6; }
  .countdown-label { margin-top: 7px; }
  .week { text-align: right; }
  .week-label { font-size: 11px; color: var(--secondary-text-color, #617270); }
  .week-number { display: block; font-size: 22px; font-weight: 500; margin-top: 3px; white-space: nowrap; }
  .forecast { padding: 16px; margin-top: 22px; border-radius: 14px; background: var(--secondary-background-color, #f3f5f0); }
  .forecast-top { display: flex; justify-content: space-between; align-items: center; gap: 8px; margin-bottom: 8px; }
  .forecast-title { font-size: 11px; font-weight: 600; letter-spacing: .04em; }
  .estimate { color: var(--secondary-text-color, #617270); font-size: 10px; border: 1px solid var(--divider-color, #cdd8cf); border-radius: 20px; padding: 3px 7px; }
  .range { font-size: clamp(14px, 4.1cqi, 18px); font-weight: 500; line-height: 1.6; }
  .forecast-note { margin: 6px 0 0; font-size: 11px; }
  .status-button { display: block; width: 100%; text-align: left; padding: 0; border: 0; color: inherit; background: none; cursor: pointer; margin-top: 24px; }
  .status-label { display: block; margin-bottom: 6px; font-size: 10px; letter-spacing: .14em; color: var(--secondary-text-color, #617270); }
  .status-text { font-size: 15px; font-weight: 500; line-height: 1.5; }
  .timeline { display: grid; grid-template-columns: repeat(4, 1fr); list-style: none; padding: 0; margin: 20px 0 24px; }
  .timeline li { position: relative; font-size: 10px; line-height: 1.4; color: var(--secondary-text-color, #617270); padding-top: 24px; }
  .timeline li::before { content: ""; position: absolute; top: 4px; left: 0; right: 0; height: 2px; background: var(--divider-color, #e0e6df); }
  .timeline li:last-child::before { display: none; }
  .timeline li::after { content: ""; position: absolute; left: 0; top: 0; height: 10px; width: 10px; border-radius: 50%; background: var(--divider-color, #d6ded7); }
  .timeline li.complete::after, .timeline li.complete::before { background: #719c80; }
  .timeline li[aria-current="step"] { color: var(--primary-text-color, #172c2d); font-weight: 600; }
  .timeline li[aria-current="step"]::after { background: #abc98e; box-shadow: 0 0 0 4px #abc98e33; }
  .insights { border-top: 1px solid var(--divider-color, #e0e6df); padding: 22px 0; }
  .insights-heading { display: flex; justify-content: space-between; gap: 12px; align-items: start; }
  .insights-heading h2 { font-size: 15px; margin: 0; font-weight: 600; }
  .insights-kicker { font-size: 10px; text-transform: uppercase; letter-spacing: .12em; color: var(--secondary-text-color, #617270); margin: 0 0 6px; }
  .insights-badge { border-radius: 20px; background: #e8f1e5; color: #295943; padding: 6px 9px; font-size: 10px; font-weight: 600; white-space: nowrap; }
  .insights-badge.changed { background: #fbf0d7; color: #775415; }
  .insights-caption { margin: 8px 0 16px; }
  .insight-stats { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
  .insight-stat { padding: 12px; border-radius: 12px; background: var(--secondary-background-color, #f3f5f0); min-width: 0; }
  .insight-stat strong { display: block; font-size: 21px; font-weight: 500; margin: 4px 0; }
  .insight-stat span { display: block; font-size: 10px; line-height: 1.4; color: var(--secondary-text-color, #617270); }
  .insight-panel { margin-top: 14px; padding: 14px; border: 1px solid var(--divider-color, #e0e6df); border-radius: 14px; }
  .insight-panel h3 { font-size: 12px; margin: 0 0 4px; font-weight: 600; }
  .insight-panel p { margin: 0; font-size: 10px; }
  .forecast-graph { width: 100%; height: auto; margin: 12px 0 2px; display: block; overflow: visible; }
  .forecast-graph text { font-size: 9px; fill: var(--secondary-text-color, #617270); font-family: inherit; }
  .forecast-graph line { stroke: var(--divider-color, #e0e6df); stroke-width: 1; }
  .forecast-graph polyline { fill: none; stroke: #4a8069; stroke-width: 3; stroke-linejoin: round; }
  .forecast-graph circle { fill: #4a8069; stroke: var(--card-background-color, white); stroke-width: 2; }
  .activity-bars { display: grid; gap: 9px; margin-top: 14px; }
  .activity-row { display: grid; grid-template-columns: 90px 1fr 20px; align-items: center; gap: 8px; font-size: 11px; }
  .activity-track { height: 7px; background: var(--secondary-background-color, #eef2ea); border-radius: 10px; overflow: hidden; }
  .activity-fill { height: 100%; border-radius: inherit; background: #719c80; }
  .activity-count { text-align: right; font-variant-numeric: tabular-nums; }
  .history-list { list-style: none; margin: 0; padding: 0; }
  .history-list li { padding: 12px 0; border-top: 1px solid var(--divider-color, #e0e6df); }
  .history-list li:first-child { border-top: 0; }
  .history-list time { display: block; font-size: 10px; color: var(--secondary-text-color, #617270); margin-bottom: 5px; }
  .history-list strong { font-size: 11px; display: block; margin-top: 6px; }
  .history-list p { font-size: 11px; line-height: 1.5; margin: 3px 0 0; overflow-wrap: anywhere; }
  .history-list .before { color: var(--secondary-text-color, #617270); }
  .history-empty { padding: 14px 0 0; font-size: 11px; line-height: 1.6; color: var(--secondary-text-color, #617270); }
  details { border-top: 1px solid var(--divider-color, #e0e6df); padding: 16px 0; }
  summary { cursor: pointer; font-size: 12px; line-height: 1.6; }
  .changes-text { white-space: pre-line; }
  .vehicle-specification { font-size: 13px; font-weight: 500; line-height: 1.7; overflow-wrap: anywhere; }
  .vehicle-note { font-size: 11px; }
  .vehicle-gallery { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; margin: 14px 0; }
  .vehicle-gallery figure { margin: 0; border-radius: 10px; overflow: hidden; background: #f4f5f2; color: #233e3b; }
  .vehicle-gallery img { display: block; width: 100%; aspect-ratio: 16 / 10; object-fit: contain; }
  .vehicle-gallery figcaption { font-size: 10px; padding: 7px 10px; }
  .vehicle-links { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 16px; }
  .vehicle-links a { color: inherit; text-decoration: none; font-size: 12px; padding: 9px 12px; border: 1px solid var(--divider-color, #d6ded7); border-radius: 20px; }
  .footer { display: flex; justify-content: space-between; gap: 12px; padding-top: 16px; border-top: 1px solid var(--divider-color, #e0e6df); align-items: center; }
  .updated { font-size: 10px; line-height: 1.7; color: var(--secondary-text-color, #617270); }
  .refresh { border: 1px solid var(--divider-color, #d6ded7); border-radius: 50%; width: 40px; height: 40px; flex-shrink: 0; cursor: pointer; color: inherit; background: transparent; font-size: 22px; }
  .refresh:disabled { opacity: .4; cursor: default; }
  .notice { margin: 0 0 20px; font-size: 12px; line-height: 1.6; padding: 12px 14px; border: 1px solid var(--warning-color, #c8933e); border-radius: 12px; }
  .action-error { color: var(--error-color, #bc4444); margin: 12px 0 0; font-size: 12px; }
  @container (max-width: 340px) { .hero { padding: 22px 20px 0; } .body { padding: 22px 20px; } .scene { width: calc(100% + 40px); margin-inline: -20px; } .week-number { font-size: 18px; } }
`;

const TEMPLATE = `
  <ha-card>
    <header class="hero">
      <div class="topline"><span class="eyebrow">Volvo · Leveransresan</span><span class="model"></span></div>
      <h1>Snart på<br>din uppfart.</h1>
      <p class="subtitle"></p>
      <figure class="vehicle-photo" hidden>
        <img class="main-image" referrerpolicy="no-referrer" decoding="async" hidden>
        <figcaption>Bild från Volvos leveranssida · kan vara en modellillustration</figcaption>
      </figure>
      <p class="image-notice" role="status" hidden></p>
      <svg class="scene" viewBox="0 0 520 128" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
        <path fill="#ffffff05" d="M0 80 90 12 183 82 310 2 437 91 520 28V128H0Z"/>
        <path fill="#ffffff06" d="m0 118 160-60 105 53L404 45l116 70v13H0Z"/>
        <path stroke="#aac4af" stroke-opacity=".22" fill="none" d="M0 110h520M0 120h520"/>
        <ellipse cx="273" cy="111" rx="157" ry="7" fill="#071c1d" opacity=".5"/>
        <path d="m128 91 23-26q6-7 19-9l71-4q24 0 43 12l34 19 52 5q16 2 22 13l-2 6H119l1-8q1-5 8-8Z" fill="#d4ddd4"/>
        <path d="m159 66 15-6 62-3q24 0 41 12l24 14-148-1Z" fill="#294748"/>
        <path d="m219 58 2 24m60-13-3 14" stroke="#c6d3c9" stroke-width="4"/>
        <path d="m128 92 250 5m-160-9v17m94-17 3 16" stroke="#889e94" fill="none"/>
        <path d="m124 96 16 1m229-2 16 4" stroke="#f4f4ce" stroke-width="4" stroke-linecap="round"/>
        <g fill="#132f31" stroke="#bdcbc0" stroke-width="3">
          <circle cx="170" cy="104" r="15"/><circle cx="339" cy="104" r="15"/>
        </g>
        <g fill="#a9bbb0"><circle cx="170" cy="104" r="7"/><circle cx="339" cy="104" r="7"/></g>
      </svg>
    </header>
    <div class="body">
      <p class="notice" role="status" hidden></p>
      <div class="countdown">
        <div><div><span class="number">–</span><span class="unit">dagar</span></div><div class="muted countdown-label">till leveransveckan börjar</div></div>
        <div class="week"><span class="week-label">LEVERANSVECKA</span><span class="week-number">–</span></div>
      </div>
      <section class="forecast" aria-label="Leveransprognos">
        <div class="forecast-top"><span class="forecast-title">Ditt beräknade leveransfönster</span><span class="estimate">Prognos</span></div>
        <div class="range"></div><p class="muted forecast-note"></p>
      </section>
      <button class="status-button" type="button" aria-label="Visa mer information om leveransstatus">
        <span class="status-label">JUST NU</span><span class="status-text"></span>
      </button>
      <ol class="timeline" aria-label="Leveranssteg">
        <li>Beställd</li><li>Byggd</li><li>På väg</li><li>Levererad</li>
      </ol>
      <section class="insights" aria-label="Leveranshistorik och statistik">
        <div class="insights-heading">
          <div><p class="insights-kicker">Din leverans över tid</p><h2>Ändringar &amp; prognos</h2></div>
          <span class="insights-badge"></span>
        </div>
        <p class="muted insights-caption"></p>
        <div class="insight-stats">
          <div class="insight-stat"><span>REGISTRERADE ÄNDRINGAR</span><strong class="insight-total">–</strong><span>sedan historiken började</span></div>
          <div class="insight-stat"><span>SENASTE PROGNOSSKIFTE</span><strong class="insight-shift">–</strong><span class="insight-shift-note">jämförda leveransveckor</span></div>
        </div>
        <div class="insight-panel">
          <h3>Leveransprognos över tid</h3>
          <p class="muted">Veckans start vid varje prognosskifte. Punkterna visas i ordning med jämnt avstånd.</p>
          <svg class="forecast-graph" viewBox="0 0 300 130" role="img" aria-label="Tidigare och aktuell prognos för leveransveckans start" hidden></svg>
          <div class="history-empty graph-empty"></div>
        </div>
        <div class="insight-panel">
          <h3>Vad har ändrats?</h3>
          <p class="muted activity-caption"></p>
          <div class="activity-bars"></div>
        </div>
        <div class="insight-panel">
          <h3>Senaste ändringarna</h3>
          <p class="muted history-caption"></p>
          <ol class="history-list"></ol>
          <div class="history-empty list-empty"></div>
        </div>
      </section>
      <details class="vehicle-details" hidden>
        <summary>Din bil · konfiguration och bilder</summary>
        <p class="vehicle-specification"></p>
        <p class="muted vehicle-note">Konfigurationstext från Volvo. Svaret innehåller inte en fullständig utrustningslista eller ett VIN. Bilderna kan vara generella modellbilder.</p>
        <div class="vehicle-gallery">
          <figure class="rear-photo" hidden><img class="rear-image" loading="lazy" decoding="async" referrerpolicy="no-referrer" hidden><figcaption>Exteriör · bild från Volvo</figcaption></figure>
          <figure class="interior-photo" hidden><img class="interior-image" loading="lazy" decoding="async" referrerpolicy="no-referrer" hidden><figcaption>Interiör · bild från Volvo</figcaption></figure>
        </div>
        <p class="muted gallery-notice" role="status" hidden></p>
        <nav class="vehicle-links" aria-label="Volvos bilinformation">
          <a class="model-link" target="_blank" rel="noopener noreferrer" hidden>Utforska modellen ↗</a>
          <a class="manual-link" target="_blank" rel="noopener noreferrer" hidden>Manual och support ↗</a>
        </nav>
      </details>
      <details class="order-details" hidden><summary>Information om din order</summary><p class="muted changes-text"></p></details>
      <footer class="footer"><div class="updated"></div><button class="refresh" type="button" aria-label="Uppdatera leveransinformation" title="Uppdatera leveransinformation">↻</button></footer>
      <p class="action-error" role="alert" hidden></p>
    </div>
  </ha-card>
`;

class VolvoDeliveryCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this.shadowRoot.innerHTML = `<style>${STYLES}</style>${TEMPLATE}`;
    this._failedImages = new Set();
    for (const selector of [".main-image", ".rear-image", ".interior-image"]) {
      this.shadowRoot
        .querySelector(selector)
        .addEventListener("error", (event) => {
          this._failedImages.add(event.target.getAttribute("src"));
          this._render();
        });
    }
    this.shadowRoot
      .querySelector(".refresh")
      .addEventListener("click", () => this._refresh());
    this.shadowRoot
      .querySelector(".status-button")
      .addEventListener("click", () => {
        if (this._config?.status_entity) {
          this.dispatchEvent(
            new CustomEvent("hass-more-info", {
              detail: { entityId: this._config.status_entity },
              bubbles: true,
              composed: true,
            }),
          );
        }
      });
  }

  static getConfigElement() {
    return document.createElement("volvo-delivery-card-editor");
  }

  static getStubConfig(hass) {
    const status = Object.keys(hass?.states || {}).find(
      (id) => hass.states[id].attributes.delivery_field === "status",
    );
    return { type: "custom:volvo-delivery-card", status_entity: status || "" };
  }

  setConfig(config) {
    if (
      !config ||
      typeof config.status_entity !== "string" ||
      !config.status_entity.startsWith("sensor.")
    ) {
      throw new Error("Välj en Volvo Delivery-sensor för leveransstatus.");
    }
    for (const key of Object.keys(ENTITY_FIELDS)) {
      if (
        config[key] &&
        (typeof config[key] !== "string" || !config[key].startsWith("sensor."))
      ) {
        throw new Error(`${LABELS[key]} måste vara en sensor.`);
      }
    }
    this._config = { ...config };
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render(false);
  }

  connectedCallback() {
    if (!this._timer)
      this._timer = setInterval(() => this._render(false), 60000);
    this._render(false);
  }

  disconnectedCallback() {
    clearInterval(this._timer);
    this._timer = null;
  }

  getCardSize() {
    return 8;
  }

  getGridOptions() {
    return { columns: 12, min_columns: 6, rows: "auto" };
  }

  _text(selector, value) {
    const node = this.shadowRoot.querySelector(selector);
    const text = String(value ?? "");
    if (node.textContent !== text) node.textContent = text;
  }

  _timestamp(entity) {
    if (!isAvailable(entity)) return null;
    const date = new Date(entity.state);
    if (Number.isNaN(date.getTime())) return null;
    return new Intl.DateTimeFormat("sv-SE", {
      dateStyle: "short",
      timeStyle: "short",
      timeZone: this._hass.config?.time_zone || "Europe/Stockholm",
    }).format(date);
  }

  _image(selector, value, alt) {
    const image = this.shadowRoot.querySelector(selector);
    const url = volvoUrl(value, true);
    const visible = Boolean(url && !this._failedImages.has(url));
    image.hidden = !visible;
    image.parentElement.hidden = !visible;
    if (image.alt !== alt) image.alt = alt;
    if (visible && image.getAttribute("src") !== url) {
      image.setAttribute("src", url);
    } else if (!visible) {
      image.removeAttribute("src");
    }
    return visible;
  }

  _vehicle(status) {
    const attributes = isAvailable(status) ? status.attributes : {};
    const mainVisible = this._image(
      ".main-image",
      attributes.image_url,
      attributes.image_alt || attributes.model || "Bilbild från Volvo",
    );
    this.shadowRoot
      .querySelector(".scene")
      .toggleAttribute("hidden", mainVisible);
    const imageNotice = this.shadowRoot.querySelector(".image-notice");
    imageNotice.hidden = mainVisible;
    this._text(
      ".image-notice",
      attributes.image_url
        ? "Volvos bilbild kunde inte visas. En generell illustration visas i stället."
        : "Volvo har inte skickat någon bilbild. Illustrationen är generell.",
    );
    const rear = this._image(
      ".rear-image",
      attributes.rear_image_url,
      "Exteriörbild från Volvo",
    );
    const interior = this._image(
      ".interior-image",
      attributes.interior_image_url,
      "Interiörbild från Volvo",
    );
    const failedGallery =
      (attributes.rear_image_url && !rear) ||
      (attributes.interior_image_url && !interior);
    this.shadowRoot.querySelector(".gallery-notice").hidden = !failedGallery;
    this._text(
      ".gallery-notice",
      "En eller flera av Volvos extrabilder kunde inte visas.",
    );
    this.shadowRoot.querySelector(".vehicle-gallery").hidden =
      !rear && !interior;
    let hasLink = false;
    for (const [selector, value] of [
      [".model-link", attributes.model_url],
      [".manual-link", attributes.manual_url],
    ]) {
      const link = this.shadowRoot.querySelector(selector);
      const url = volvoUrl(value);
      link.hidden = !url;
      if (url) {
        if (link.getAttribute("href") !== url) link.href = url;
        hasLink = true;
      } else {
        link.removeAttribute("href");
      }
    }
    this._text(
      ".vehicle-specification",
      attributes.specification || attributes.model || "",
    );
    this.shadowRoot.querySelector(".vehicle-details").hidden = !(
      attributes.specification ||
      rear ||
      interior ||
      hasLink
    );
  }

  _history(status) {
    const attrs = isAvailable(status) ? status.attributes : {};
    const history = Array.isArray(attrs.change_history)
      ? attrs.change_history.filter(
          (item) =>
            item &&
            Array.isArray(item.changes) &&
            !Number.isNaN(Date.parse(item.at)),
        )
      : [];
    const events = history.filter(
      (item) => !item.baseline && item.changes.length,
    );
    const total =
      Number.isSafeInteger(attrs.history_total) && attrs.history_total >= 0
        ? attrs.history_total
        : null;
    const started = Date.parse(attrs.history_started);
    const formatDate = (value) =>
      new Intl.DateTimeFormat("sv-SE", {
        dateStyle: "medium",
        timeZone: this._hass.config?.time_zone || "Europe/Stockholm",
      }).format(new Date(value));
    const formatDay = (day) =>
      new Intl.DateTimeFormat("sv-SE", {
        day: "numeric",
        month: "short",
        year: "numeric",
        timeZone: "UTC",
      }).format(day);
    const startedText = Number.isNaN(started) ? null : formatDate(started);
    const badge = this.shadowRoot.querySelector(".insights-badge");
    badge.classList.toggle("changed", Boolean(total));
    this._text(
      ".insights-badge",
      total === null
        ? "Ingen historik"
        : total
          ? "Ändringar finns"
          : "Inga ändringar",
    );
    this._text(
      ".insights-caption",
      startedText
        ? `Registreras sedan ${startedText}. Äldre ändringar finns inte med.`
        : "Historik börjar samlas när integrationen uppdateras. Äldre ändringar finns inte med.",
    );
    this._text(".insight-total", total === null ? "–" : total);

    const points = [];
    for (const item of history) {
      const forecast = calendarDay(item.forecast_start);
      if (!forecast) continue;
      if (
        points.length &&
        points[points.length - 1].forecast.getTime() === forecast.getTime()
      )
        continue;
      points.push({ forecast, at: item.at });
    }
    let shift = null;
    for (let i = history.length - 1; i > 0; i--) {
      const previous = calendarDay(history[i - 1].forecast_start);
      const current = calendarDay(history[i].forecast_start);
      if (!previous || !current) continue;
      const delta = Math.round((current - previous) / 86400000);
      if (delta) {
        shift = delta;
        break;
      }
    }
    this._text(
      ".insight-shift",
      shift === null ? "–" : `${shift > 0 ? "+" : "−"}${Math.abs(shift)} d`,
    );
    this._text(
      ".insight-shift-note",
      shift === null
        ? "inget jämförbart skifte ännu"
        : shift > 0
          ? "senare än förra prognosen"
          : "tidigare än förra prognosen",
    );

    const svg = this.shadowRoot.querySelector(".forecast-graph");
    svg.replaceChildren();
    svg.toggleAttribute("hidden", points.length < 2);
    this._text(
      ".graph-empty",
      points.length < 2
        ? "Diagrammet visas när två olika daterade leveransprognoser har registrerats."
        : "",
    );
    if (points.length >= 2) {
      const shown = points.slice(-10);
      const values = shown.map((point) => point.forecast.getTime());
      const min = Math.min(...values);
      const max = Math.max(...values);
      const svgElement = (name, attributes, text) => {
        const element = document.createElementNS(
          "http://www.w3.org/2000/svg",
          name,
        );
        for (const [key, value] of Object.entries(attributes))
          element.setAttribute(key, String(value));
        if (text !== undefined) element.textContent = text;
        svg.append(element);
        return element;
      };
      svgElement("line", { x1: 12, y1: 26, x2: 288, y2: 26 });
      svgElement("line", { x1: 12, y1: 88, x2: 288, y2: 88 });
      const coords = shown.map((point, index) => ({
        x: 16 + (index * 268) / (shown.length - 1),
        y: 88 - ((point.forecast.getTime() - min) * 62) / (max - min),
      }));
      svgElement("polyline", {
        points: coords.map(({ x, y }) => `${x},${y}`).join(" "),
      });
      for (const { x, y } of coords)
        svgElement("circle", { cx: x, cy: y, r: 4 });
      svgElement(
        "text",
        { x: 12, y: 16 },
        `Senare: ${formatDay(new Date(max))}`,
      );
      svgElement(
        "text",
        { x: 12, y: 105 },
        `Tidigare: ${formatDay(new Date(min))}`,
      );
      svgElement("text", { x: 12, y: 125 }, formatDate(shown[0].at));
      svgElement(
        "text",
        { x: 288, y: 125, "text-anchor": "end" },
        formatDate(shown[shown.length - 1].at),
      );
    }

    const categories = [
      ["Prognos", ["forecast", "forecast_date"]],
      ["Status", ["status"]],
      ["Order", ["order", "order_description"]],
      ["Bil", ["model", "specification"]],
      ["Bilder", ["media"]],
    ];
    const bars = this.shadowRoot.querySelector(".activity-bars");
    bars.replaceChildren();
    const counts = categories.map(
      ([, fields]) =>
        events.filter((event) =>
          event.changes.some((change) => fields.includes(change.field)),
        ).length,
    );
    const peak = Math.max(...counts, 1);
    categories.forEach(([label], index) => {
      const row = document.createElement("div");
      row.className = "activity-row";
      const name = document.createElement("span");
      name.textContent = label;
      const track = document.createElement("div");
      track.className = "activity-track";
      const fill = document.createElement("div");
      fill.className = "activity-fill";
      fill.style.width = `${(counts[index] / peak) * 100}%`;
      track.append(fill);
      const count = document.createElement("span");
      count.className = "activity-count";
      count.textContent = String(counts[index]);
      row.append(name, track, count);
      bars.append(row);
    });
    this._text(
      ".activity-caption",
      `Antal händelser per kategori i de ${history.length} sparade historikpunkterna. En händelse kan ingå i flera kategorier.`,
    );
    const list = this.shadowRoot.querySelector(".history-list");
    list.replaceChildren();
    const labels = {
      status: "Status",
      forecast: "Leveransprognos",
      forecast_date: "Beräknad veckostart",
      order: "Orderändringar",
      order_description: "Orderinformation",
      specification: "Bilkonfiguration",
      model: "Bilmodell",
      media: "Bilder och länkar",
    };
    for (const event of events.slice(-5).reverse()) {
      const li = document.createElement("li");
      const time = document.createElement("time");
      time.dateTime = event.at;
      time.textContent = formatDate(event.at);
      li.append(time);
      for (const change of event.changes) {
        if (!labels[change.field]) continue;
        const heading = document.createElement("strong");
        heading.textContent = labels[change.field];
        const before = document.createElement("p");
        before.className = "before";
        before.textContent = `Tidigare: ${change.before || "Saknas"}`;
        const after = document.createElement("p");
        after.textContent = `Nu: ${change.after || "Saknas"}`;
        li.append(heading, before, after);
      }
      list.append(li);
    }
    this._text(
      ".history-caption",
      events.length
        ? `Senaste ${Math.min(events.length, 5)} av ${events.length} sparade händelser.`
        : "",
    );
    this._text(
      ".list-empty",
      !startedText
        ? "Ingen historik är tillgänglig ännu."
        : events.length
          ? ""
          : "Inga ändringar har upptäckts sedan registreringen började.",
    );
  }

  _render(force = true) {
    if (!this._config || !this._hass) return;
    const entities = resolveEntities(this._hass, this._config);
    const timeZone = this._hass.config?.time_zone || "Europe/Stockholm";
    const now = new Date();
    const day = todayInZone(now, timeZone).getTime();
    if (
      !force &&
      this._renderedTimeZone === timeZone &&
      this._renderedDay === day &&
      Object.entries(entities).every(
        ([key, { id, entity }]) =>
          this._entities[key].id === id &&
          this._entities[key].entity === entity,
      )
    )
      return;
    this._renderedTimeZone = timeZone;
    this._renderedDay = day;
    const vehicleChanged =
      this._entities?.status_entity.entity !== entities.status_entity.entity;
    this._entities = entities;
    const status = entities.status_entity.entity;
    if (force || vehicleChanged) {
      this._vehicle(status);
      this._history(status);
    }
    const estimate = entities.delivery_entity.entity;
    const available = isAvailable(status) && isAvailable(estimate);
    const forecast = available ? forecastView(estimate, day) : null;
    const delivered =
      isAvailable(status) && stageIndex(entityText(status)) === 3;
    const model = status?.attributes.model || "Din Volvo";
    this._text(".model", model);
    this._text(
      "h1",
      delivered
        ? "Välkommen hem."
        : this._config.title || "Snart på din uppfart.",
    );
    this._text(
      ".subtitle",
      status?.attributes.specification ||
        "Följ din nästa resa, hela vägen från beställning till leverans.",
    );
    const notice = this.shadowRoot.querySelector(".notice");
    notice.hidden = available;
    this._text(
      ".notice",
      !status
        ? "Statussensorn hittades inte. Välj din Volvo Delivery-sensor i kortets inställningar."
        : !isAvailable(status)
          ? "Leveransuppgifterna är inte tillgängliga. Kontrollera integrationens anslutning och behörighet."
          : "Leveransprognosen är inte tillgänglig. Kontrollera att leveranssensorn är aktiverad.",
    );
    this._text(
      ".number",
      delivered || !forecast || forecast.phase === "past" ? "–" : forecast.days,
    );
    this._text(".unit", forecast?.days === 1 ? "dag" : "dagar");
    this._text(
      ".countdown-label",
      delivered
        ? "din bil är levererad"
        : !available
          ? "väntar på leveransuppgifter"
          : !forecast
            ? "nedräkning saknar säkert datumunderlag"
            : forecast.phase === "current"
              ? "din beräknade leveransvecka pågår"
              : forecast.phase === "past"
                ? "prognosveckan har passerat"
                : "till leveransveckan börjar",
    );
    const week = forecast && estimate.attributes.delivery_week;
    this._text(".week-number", week ? `v. ${week}` : "–");
    this._text(
      ".range",
      forecast
        ? forecast.range
        : entityText(estimate) || "Ingen leveransprognos ännu",
    );
    this._text(
      ".forecast-note",
      !available
        ? "Ingen aktuell prognos kan visas."
        : !forecast
          ? "Volvos uppgifter räcker inte för ett datumintervall. Inget exakt datum gissas."
          : `${estimate.attributes.year_source === "inferred" ? "Årtalet är uppskattat från Volvos veckoprognos. " : ""}Avser måndag–söndag, inte ett bekräftat leveransdatum.`,
    );
    this._text(".status-text", entityText(status) || "Inväntar uppdatering");
    const stage = isAvailable(status) ? stageIndex(entityText(status)) : -1;
    for (const [index, item] of [
      ...this.shadowRoot.querySelectorAll(".timeline li"),
    ].entries()) {
      item.classList.toggle("complete", index < stage);
      if (index === stage) item.setAttribute("aria-current", "step");
      else item.removeAttribute("aria-current");
    }
    const changes = entities.changes_entity.entity;
    const details = this.shadowRoot.querySelector(".order-details");
    details.hidden = !entityText(changes);
    this._text(
      ".changes-text",
      [entityText(changes), changes?.attributes.description]
        .filter(Boolean)
        .join("\n\n"),
    );
    const checked = this._timestamp(entities.last_checked_entity.entity);
    const changed = this._timestamp(entities.last_changed_entity.entity);
    this._text(
      ".updated",
      [
        checked
          ? `Kontrollerad ${checked}`
          : "Ingen lyckad kontroll tillgänglig",
        changed ? `Senast ändrad ${changed}` : null,
      ]
        .filter(Boolean)
        .join(" · "),
    );
    const button = this.shadowRoot.querySelector(".refresh");
    button.disabled = this._refreshing || !status;
    button.setAttribute("aria-busy", String(Boolean(this._refreshing)));
  }

  async _refresh() {
    if (this._refreshing || !this._entities?.status_entity.entity) return;
    this._refreshing = true;
    const error = this.shadowRoot.querySelector(".action-error");
    error.hidden = true;
    this._render();
    try {
      await this._hass.callService("homeassistant", "update_entity", {
        entity_id: this._config.status_entity,
      });
    } catch {
      error.textContent =
        "Kunde inte begära en uppdatering. Kontrollera din anslutning och behörighet i Home Assistant.";
      error.hidden = false;
    } finally {
      this._refreshing = false;
      this._render();
    }
  }
}

class VolvoDeliveryCardEditor extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
  }

  setConfig(config) {
    this._config = { ...config };
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    const signature = JSON.stringify(
      Object.entries(hass.states)
        .filter(([, state]) => state.attributes.delivery_field)
        .map(([id, state]) => [id, state.attributes.friendly_name]),
    );
    if (signature !== this._optionSignature) {
      this._optionSignature = signature;
      this._render();
    }
  }

  _render() {
    if (!this._config || !this._hass) return;
    this.shadowRoot.innerHTML = `
      <style>
        :host { display: grid; gap: 18px; padding: 8px 0; }
        label { display: grid; gap: 8px; font-size: 14px; }
        input, select { font: inherit; padding: 12px; border: 1px solid var(--divider-color, #aaa); border-radius: 8px; color: var(--primary-text-color, #222); background: var(--card-background-color, #fff); width: 100%; }
        p { font-size: 13px; line-height: 1.6; color: var(--secondary-text-color, #666); margin: 0; }
      </style>
      <p>Välj din order. Övriga sensorer hittas automatiskt för samma order, oavsett entitetsnamn. Datum och nedräkning är en prognos, inte en leveransgaranti.</p>
      <label>Rubrik<input type="text" placeholder="Snart på din uppfart."></label>
    `;
    const title = this.shadowRoot.querySelector("input");
    title.value = this._config.title || "";
    title.addEventListener("change", () => this._change("title", title.value));
    for (const [key, field] of Object.entries(ENTITY_FIELDS)) {
      const label = document.createElement("label");
      label.append(document.createTextNode(LABELS[key]));
      const select = document.createElement("select");
      select.setAttribute("aria-label", LABELS[key]);
      const empty = document.createElement("option");
      empty.value = "";
      empty.textContent =
        key === "status_entity"
          ? "Välj orderns statussensor"
          : "Automatiskt från samma order";
      select.append(empty);
      const ids = Object.keys(this._hass.states).filter(
        (id) =>
          this._hass.states[id].attributes.delivery_field === field ||
          id === this._config[key],
      );
      for (const id of ids.sort()) {
        const option = document.createElement("option");
        option.value = id;
        option.textContent =
          this._hass.states[id].attributes.friendly_name || id;
        select.append(option);
      }
      select.value = this._config[key] || "";
      select.addEventListener("change", () => this._change(key, select.value));
      label.append(select);
      this.shadowRoot.append(label);
    }
  }

  _change(key, value) {
    const config = { ...this._config };
    if (value) config[key] = value;
    else delete config[key];
    if (key === "status_entity") {
      for (const field of Object.keys(ENTITY_FIELDS)) {
        if (field !== key) delete config[field];
      }
    }
    this._config = config;
    this.dispatchEvent(
      new CustomEvent("config-changed", {
        detail: { config },
        bubbles: true,
        composed: true,
      }),
    );
  }
}

if (!customElements.get("volvo-delivery-card")) {
  customElements.define("volvo-delivery-card", VolvoDeliveryCard);
}
if (!customElements.get("volvo-delivery-card-editor")) {
  customElements.define("volvo-delivery-card-editor", VolvoDeliveryCardEditor);
}
window.customCards = window.customCards || [];
if (!window.customCards.some((card) => card.type === "volvo-delivery-card")) {
  window.customCards.push({
    type: "volvo-delivery-card",
    name: "Volvo Delivery",
    description:
      "Din Volvoleverans med nedräkning, leveransfönster och status.",
    preview: true,
  });
}
