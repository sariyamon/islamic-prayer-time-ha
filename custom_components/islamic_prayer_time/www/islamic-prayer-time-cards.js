/*!
 * Islamic Prayer Time cards for Home Assistant
 * https://github.com/sariyamon/islamic-prayer-time-ha
 *
 * Cards:
 *   custom:islamic-prayer-times-card   Tiles     – the classic six-tile layout
 *   custom:islamic-prayer-compact-card Compact   – next prayer + progress bar
 *   custom:islamic-lantern-glow-card   Lantern Glow  – one large lantern, next prayer focus
 *   custom:islamic-lantern-night-card  Lantern Night – six lanterns on a garland under a night sky
 *   custom:islamic-lantern-arch-card   Lantern Arch  – mihrab arch with a lantern timeline
 *
 * Every card auto-discovers the entities of the Islamic Prayer Time
 * integration (and falls back to the core Islamic Prayer Times integration).
 * MIT licence.
 */

const VERSION = "1.0.0";
const DOMAIN = "islamic_prayer_time";
const CORE_DOMAIN = "islamic_prayer_times";
const PRAYERS = ["fajr", "sunrise", "dhuhr", "asr", "maghrib", "isha"];

const NAMES = {
  fajr: "Fajr", sunrise: "Sunrise", dhuhr: "Dhuhr",
  asr: "Asr", maghrib: "Maghrib", isha: "Isha",
};
const ARABIC = {
  fajr: "الفجر", sunrise: "الشروق", dhuhr: "الظهر",
  asr: "العصر", maghrib: "المغرب", isha: "العشاء",
};
const ICONS = {
  fajr: "mdi:weather-night-partly-cloudy",
  sunrise: "mdi:weather-sunset-up",
  dhuhr: "mdi:white-balance-sunny",
  asr: "mdi:weather-partly-cloudy",
  maghrib: "mdi:weather-sunset-down",
  isha: "mdi:weather-night",
};

/* Lantern palette – brass, lamp light and night-sky lapis. */
const C = {
  ink: "#141a33",
  lapis: "#24336e",
  brass: "#c9a24a",
  brassDeep: "#8a6a24",
  lamp: "#ffb547",
  ember: "#ff8a3d",
  parchment: "#f3e9d2",
  iznik: "#2f7c77",
};

/* ------------------------------------------------------------------ fonts */
(function loadFonts() {
  if (document.getElementById("ipt-fonts")) return;
  const link = document.createElement("link");
  link.id = "ipt-fonts";
  link.rel = "stylesheet";
  link.href =
    "https://fonts.googleapis.com/css2?family=Reem+Kufi:wght@500;700&display=swap";
  document.head.appendChild(link);
})();
const KUFI = `"Reem Kufi", "Noto Kufi Arabic", "Segoe UI", serif`;

/* ---------------------------------------------------------------- helpers */
function fireEvent(node, type, detail) {
  node.dispatchEvent(
    new CustomEvent(type, { detail, bubbles: true, composed: true })
  );
}

function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[c]);
}

/** Find the entities for one prayer-time location. */
function discoverEntities(hass, config) {
  const map = {};
  const reg = hass.entities || {};
  const pick = (platform) => {
    const found = {};
    for (const [id, e] of Object.entries(reg)) {
      if (e.platform !== platform || !id.startsWith("sensor.")) continue;
      if (config.device && e.device_id !== config.device) continue;
      if (e.translation_key) found[e.translation_key] = id;
    }
    return found;
  };
  let found = pick(DOMAIN);
  let source = DOMAIN;
  if (!found.fajr) {
    found = pick(CORE_DOMAIN);
    source = CORE_DOMAIN;
  }
  Object.assign(map, found, config.entities || {});
  return { map, source };
}

/** Build a normalised model from hass state. */
function buildModel(hass, config) {
  const { map, source } = discoverEntities(hass, config);
  const times = {};
  const tomorrow = {};
  let missing = [];
  for (const p of PRAYERS) {
    const st = map[p] && hass.states[map[p]];
    const d = st ? new Date(st.state) : null;
    if (!d || isNaN(d)) {
      missing.push(p);
      continue;
    }
    times[p] = d;
    const t = st.attributes && st.attributes.tomorrow;
    tomorrow[p] = t ? new Date(t) : new Date(d.getTime() + 864e5);
  }
  const hijriState = map.hijri_date && hass.states[map.hijri_date];
  return {
    map,
    source,
    missing,
    times,
    tomorrow,
    hijri: hijriState ? hijriState.state : null,
    hijriAttrs: hijriState ? hijriState.attributes : {},
  };
}

/** Current / next prayer, computed live on the client every second. */
function resolve(model, prayers, now = new Date()) {
  const list = prayers.filter((p) => model.times[p]);
  let current = "isha";
  let currentStart = model.times.isha
    ? new Date(model.times.isha.getTime() - 864e5)
    : now;
  for (const p of list) {
    if (model.times[p] <= now) {
      current = p;
      currentStart = model.times[p];
    }
  }
  let next = null;
  let nextStart = null;
  for (const p of list) {
    if (model.times[p] > now) {
      next = p;
      nextStart = model.times[p];
      break;
    }
  }
  if (!next) {
    next = list[0] || "fajr";
    nextStart = model.tomorrow[next];
  }
  const span = Math.max(1, nextStart - currentStart);
  const progress = Math.min(1, Math.max(0, (now - currentStart) / span));
  return { current, next, currentStart, nextStart, progress, remaining: nextStart - now };
}

function use12h(hass, config) {
  if (config.time_format === "12") return true;
  if (config.time_format === "24") return false;
  const tf = hass.locale && hass.locale.time_format;
  if (tf === "12") return true;
  if (tf === "24") return false;
  const lang = (hass.locale && hass.locale.language) || hass.language || "en";
  return new Intl.DateTimeFormat(lang, { hour: "numeric" }).resolvedOptions().hour12 === true;
}

function formatTime(hass, config, date) {
  if (!date) return "--:--";
  const h12 = use12h(hass, config);
  const lang = (hass.locale && hass.locale.language) || hass.language || "en";
  const opts = { hour: "2-digit", minute: "2-digit", hour12: h12 };
  const tz = hass.config && hass.config.time_zone;
  if (hass.locale && hass.locale.time_zone === "server" && tz) opts.timeZone = tz;
  const parts = new Intl.DateTimeFormat(lang, opts).formatToParts(date);
  let main = "";
  let period = "";
  for (const part of parts) {
    if (part.type === "dayPeriod") period = part.value;
    else main += part.value;
  }
  main = escapeHtml(main.trim());
  if (!period || config.show_ampm === false) return main;
  // AM/PM is set smaller so columns of times stay on one line.
  return `${main}<span class="ap">${escapeHtml(period)}</span>`;
}

function formatRemaining(ms) {
  if (ms <= 30e3) return "now";
  const totalMin = Math.ceil(ms / 60e3);
  const h = Math.floor(totalMin / 60);
  const m = totalMin % 60;
  if (h === 0) return `in ${m} min`;
  return m === 0 ? `in ${h} h` : `in ${h} h ${m} min`;
}

function label(config, p) {
  return (config.names && config.names[p]) || NAMES[p];
}

/** A Fanous lantern as SVG. state: "lit" | "past" | "idle". */
function lanternSVG(state, opts = {}) {
  const w = opts.width || 40;
  const id = opts.id || Math.random().toString(36).slice(2, 8);
  const lit = state === "lit";
  const glass = lit ? `url(#g${id})` : state === "past" ? "rgba(255,255,255,0.06)" : "rgba(255,222,160,0.18)";
  const metal = state === "past" ? "#6d6450" : C.brass;
  const metalDeep = state === "past" ? "#4a4436" : C.brassDeep;
  return `
<svg class="lantern ${state}" viewBox="0 0 40 72" width="${w}" height="${(w * 72) / 40}" aria-hidden="true">
  <defs>
    <radialGradient id="g${id}" cx="50%" cy="58%" r="60%">
      <stop offset="0%" stop-color="#fff6d8"/>
      <stop offset="35%" stop-color="${C.lamp}"/>
      <stop offset="100%" stop-color="${C.ember}" stop-opacity="0.85"/>
    </radialGradient>
    <radialGradient id="h${id}" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="${C.lamp}" stop-opacity="0.55"/>
      <stop offset="100%" stop-color="${C.lamp}" stop-opacity="0"/>
    </radialGradient>
  </defs>
  ${lit ? `<circle class="halo" cx="20" cy="42" r="22" fill="url(#h${id})"/>` : ""}
  <circle cx="20" cy="4" r="3" fill="none" stroke="${metal}" stroke-width="1.6"/>
  <path d="M12 16 Q20 4 28 16 Z" fill="${metal}"/>
  <rect x="10" y="16" width="20" height="3" rx="1" fill="${metalDeep}"/>
  <path d="M11 19 L29 19 L32 30 L32 50 L27 58 L13 58 L8 50 L8 30 Z" fill="${glass}" stroke="${metal}" stroke-width="1.4"/>
  <path d="M20 19 L20 58 M8 30 L32 30 M8 50 L32 50" stroke="${metal}" stroke-width="1" opacity="0.8"/>
  <path d="M14 30 Q14 24 17 22 M26 30 Q26 24 23 22" stroke="${metal}" stroke-width="0.8" fill="none" opacity="0.7"/>
  ${lit ? `<path class="flame" d="M20 33 C23 38 23 42 20 45 C17 42 17 38 20 33 Z" fill="#fffbe6"/>` : ""}
  <path d="M13 58 L27 58 L24 64 L16 64 Z" fill="${metal}"/>
  <path d="M18 64 L22 64 L20 70 Z" fill="${metalDeep}"/>
</svg>`;
}

/* An eight-point star (Rub el Hizb) tile used as a subtle pattern. */
const STAR_PATTERN = (color, opacity = 0.08) =>
  `url("data:image/svg+xml,${encodeURIComponent(
    `<svg xmlns='http://www.w3.org/2000/svg' width='48' height='48' viewBox='0 0 48 48'><g fill='none' stroke='${color}' stroke-opacity='${opacity}' stroke-width='1'><rect x='14' y='14' width='20' height='20'/><rect x='14' y='14' width='20' height='20' transform='rotate(45 24 24)'/><circle cx='24' cy='24' r='4'/></g></svg>`
  )}")`;

/* ============================================================ base class */
class PrayerCardBase extends HTMLElement {
  static cardType = "";
  static cardName = "";
  static editorSchema = [];

  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = {};
    this._sig = "";
    this._lastCurrent = null;
  }

  setConfig(config) {
    if (!config) throw new Error("Invalid configuration");
    this._config = { ...this.constructor.defaults(), ...config };
    this._sig = "";
    if (this._hass) this._render();
  }

  static defaults() {
    return { show_sunrise: true, time_format: "auto", show_hijri: true };
  }

  static getStubConfig() {
    return {};
  }

  static getConfigElement() {
    const el = document.createElement("islamic-prayer-card-editor");
    el.schema = this.editorSchema;
    return el;
  }

  set hass(hass) {
    this._hass = hass;
    const model = buildModel(hass, this._config);
    const sig = JSON.stringify([
      PRAYERS.map((p) => model.times[p] && model.times[p].getTime()),
      model.hijri,
      model.source,
      hass.themes && hass.themes.darkMode,
      hass.locale && hass.locale.time_format,
    ]);
    this._model = model;
    if (sig !== this._sig) {
      this._sig = sig;
      this._render();
    }
  }

  connectedCallback() {
    this._timer = setInterval(() => this._tick(), 1000);
  }

  disconnectedCallback() {
    clearInterval(this._timer);
  }

  get prayers() {
    return this._config.show_sunrise === false
      ? PRAYERS.filter((p) => p !== "sunrise")
      : PRAYERS;
  }

  _tick() {
    if (!this._model || this._model.missing.length) return;
    const r = resolve(this._model, this.prayers);
    if (r.current !== this._lastCurrent) {
      this._render();
      return;
    }
    this.shadowRoot.querySelectorAll("[data-remaining]").forEach((el) => {
      el.textContent = formatRemaining(r.remaining);
    });
    this.shadowRoot.querySelectorAll("[data-progress]").forEach((el) => {
      el.style.setProperty("--p", (r.progress * 100).toFixed(2) + "%");
    });
  }

  _render() {
    if (!this._hass) return;
    const m = this._model || buildModel(this._hass, this._config);
    if (m.missing.length === PRAYERS.length) {
      this.shadowRoot.innerHTML = this._empty();
      return;
    }
    const r = resolve(m, this.prayers);
    this._lastCurrent = r.current;
    this.shadowRoot.innerHTML = `<style>${BASE_CSS}${this.css()}</style>${this.html(m, r)}`;
    this.shadowRoot.querySelectorAll("[data-entity]").forEach((el) => {
      el.addEventListener("click", () =>
        fireEvent(this, "hass-more-info", { entityId: el.dataset.entity })
      );
      el.addEventListener("keydown", (ev) => {
        if (ev.key === "Enter" || ev.key === " ") {
          ev.preventDefault();
          fireEvent(this, "hass-more-info", { entityId: el.dataset.entity });
        }
      });
    });
  }

  _empty() {
    return `<style>${BASE_CSS}</style><ha-card><div class="empty">
      <ha-icon icon="mdi:mosque"></ha-icon>
      <div><b>No prayer times found.</b><br>Add the Islamic Prayer Time integration in Settings → Devices &amp; services, or set <code>entities:</code> on this card.</div>
    </div></ha-card>`;
  }

  t(date) {
    return formatTime(this._hass, this._config, date);
  }

  attrs(m, p) {
    const id = m.map[p];
    return id ? `data-entity="${escapeHtml(id)}" tabindex="0" role="button"` : "";
  }

  getCardSize() {
    return 3;
  }

  css() {
    return "";
  }
}

const BASE_CSS = `
  :host { display:block; }
  ha-card { display:block; overflow:hidden; height:100%; box-sizing:border-box; }
  .ap { font-size:.68em; font-weight:500; margin-left:.2em; letter-spacing:.02em; opacity:.8; }
  [role=button] { cursor:pointer; outline:none; }
  [role=button]:focus-visible { box-shadow: 0 0 0 2px var(--primary-color); }
  .num { font-variant-numeric: tabular-nums; }
  .empty { display:flex; gap:12px; align-items:flex-start; padding:16px; color:var(--secondary-text-color); line-height:1.45; }
  .empty ha-icon { color: var(--state-icon-color); }
  @media (prefers-reduced-motion: reduce) { * { animation: none !important; transition: none !important; } }
`;

/* ============================================================ 1. Tiles */
class PrayerTimesCard extends PrayerCardBase {
  static defaults() {
    return { ...super.defaults(), title: "Prayer Times", columns: 3, show_footer: true, accent: "amber" };
  }

  static editorSchema = [
    { name: "title", selector: { text: {} } },
    { name: "columns", selector: { number: { min: 2, max: 6, mode: "box" } } },
    { name: "accent", selector: { ui_color: {} } },
    COMMON_SCHEMA(),
  ];

  css() {
    return `
      ha-card { padding: 12px 12px 14px; }
      .head { display:flex; align-items:center; gap:8px; padding:4px 4px 12px; color:var(--secondary-text-color); }
      .head ha-icon { --mdc-icon-size:22px; color:var(--secondary-text-color); }
      .head .title { font-size:16px; font-weight:500; flex:1; }
      .chip { display:inline-flex; align-items:center; gap:4px; font-size:14px; color:var(--primary-text-color); }
      .chip ha-icon { --mdc-icon-size:18px; color:var(--ipt-accent); }
      .grid { display:grid; grid-template-columns: repeat(var(--cols), minmax(0,1fr)); gap:8px; }
      .tile { border:1px solid var(--divider-color); border-radius: var(--ha-card-border-radius, 12px);
        background: var(--card-background-color); padding:16px 6px 14px; text-align:center;
        display:flex; flex-direction:column; align-items:center; gap:6px; transition: border-color .2s; }
      .tile ha-icon { --mdc-icon-size:28px; color: var(--disabled-text-color, #9e9e9e); }
      .tile .n { font-size:15px; font-weight:500; color:var(--primary-text-color); }
      .tile .v { font-size:14px; color:var(--secondary-text-color); }
      .tile.past .n, .tile.past .v { opacity:.7; }
      .tile.now { border-color: var(--ipt-accent); background:
        color-mix(in srgb, var(--ipt-accent) 9%, var(--card-background-color)); }
      .tile.now ha-icon { color: var(--ipt-accent); }
      .tile.now .v { color: var(--primary-text-color); font-weight:500; }
      .badge { font-size:11px; font-weight:600; padding:1px 7px; border-radius:9px;
        background: var(--ipt-accent); color: #fff; margin-left:4px; vertical-align:2px; }
      .foot { display:flex; align-items:center; gap:10px; padding:12px 4px 0; font-size:13px; color:var(--secondary-text-color); }
      .foot b { color: var(--primary-text-color); font-weight:500; }
      .bar { flex:1; height:4px; border-radius:2px; background: var(--divider-color); overflow:hidden; }
      .bar i { display:block; height:100%; width: var(--p); background: var(--ipt-accent); border-radius:2px; }
    `;
  }

  html(m, r) {
    const c = this._config;
    const accent = haColor(c.accent);
    const tiles = this.prayers.map((p) => {
      const isNow = p === r.current;
      const past = !isNow && m.times[p] && m.times[p] < new Date() ;
      return `<div class="tile ${isNow ? "now" : past ? "past" : ""}" ${this.attrs(m, p)}>
        <ha-icon icon="${ICONS[p]}"></ha-icon>
        <div class="n">${escapeHtml(label(c, p))}${isNow ? `<span class="badge">Now</span>` : ""}</div>
        <div class="v num">${this.t(m.times[p])}</div>
      </div>`;
    }).join("");
    const cols = Math.min(Number(c.columns) || 3, this.prayers.length);
    return `<ha-card style="--ipt-accent:${accent}; --cols:${cols}">
      ${c.title !== "" ? `<div class="head"><ha-icon icon="mdi:mosque"></ha-icon><span class="title">${escapeHtml(c.title)}</span>
        <span class="chip"><ha-icon icon="mdi:clock-star-four-points-outline"></ha-icon>${escapeHtml(label(c, r.current))}</span></div>` : ""}
      <div class="grid">${tiles}</div>
      ${c.show_footer ? `<div class="foot"><span><b>${escapeHtml(label(c, r.next))}</b> <span data-remaining>${formatRemaining(r.remaining)}</span></span>
        <span class="bar" data-progress style="--p:${(r.progress * 100).toFixed(2)}%"><i></i></span>
        ${c.show_hijri && m.hijri ? `<span>${escapeHtml(m.hijri)}</span>` : ""}</div>` : ""}
    </ha-card>`;
  }

  getCardSize() {
    return 4;
  }
}

/* ============================================================ 2. Compact */
class PrayerCompactCard extends PrayerCardBase {
  static defaults() {
    return { ...super.defaults(), accent: "amber" };
  }
  static editorSchema = [{ name: "accent", selector: { ui_color: {} } }, COMMON_SCHEMA()];

  css() {
    return `
      ha-card { padding: 12px 16px; display:flex; align-items:center; gap:14px; }
      .ic { width:40px; height:40px; border-radius:50%; display:grid; place-items:center; flex:none;
        background: color-mix(in srgb, var(--ipt-accent) 18%, transparent); color: var(--ipt-accent); }
      .body { flex:1; min-width:0; }
      .row { display:flex; justify-content:space-between; align-items:baseline; gap:8px; }
      .name { font-size:15px; font-weight:500; color:var(--primary-text-color); }
      .time { font-size:15px; color:var(--primary-text-color); }
      .sub { font-size:12.5px; color:var(--secondary-text-color); margin-top:2px; }
      .bar { height:4px; border-radius:2px; background: var(--divider-color); overflow:hidden; margin-top:8px; }
      .bar i { display:block; height:100%; width:var(--p); background:var(--ipt-accent); }
    `;
  }

  html(m, r) {
    const c = this._config;
    return `<ha-card style="--ipt-accent:${haColor(c.accent)}" ${this.attrs(m, r.next)}>
      <div class="ic"><ha-icon icon="${ICONS[r.next]}"></ha-icon></div>
      <div class="body">
        <div class="row"><span class="name">${escapeHtml(label(c, r.next))}</span><span class="time num">${this.t(r.nextStart)}</span></div>
        <div class="row sub"><span data-remaining>${formatRemaining(r.remaining)}</span>
          <span>${c.show_hijri && m.hijri ? escapeHtml(m.hijri) : `${escapeHtml(label(c, r.current))} since ${this.t(r.currentStart)}`}</span></div>
        <div class="bar" data-progress style="--p:${(r.progress * 100).toFixed(2)}%"><i></i></div>
      </div>
    </ha-card>`;
  }

  getCardSize() {
    return 1;
  }
}

/* ============================================================ 3. Lantern Glow */
const SKY = {
  fajr: ["#1d2350", "#5b3f72"],
  sunrise: ["#3a4f8a", "#c98a5c"],
  dhuhr: ["#1f4f7a", "#2f7c77"],
  asr: ["#3b3a6b", "#a86b3c"],
  maghrib: ["#3a1f4d", "#b4553d"],
  isha: ["#10152e", "#24336e"],
};

class LanternGlowCard extends PrayerCardBase {
  static defaults() {
    return { ...super.defaults(), show_arabic: true };
  }
  static editorSchema = [{ name: "show_arabic", selector: { boolean: {} } }, COMMON_SCHEMA()];

  css() {
    return `
      ha-card { color: ${C.parchment}; border:none; position:relative; isolation:isolate;
        background: linear-gradient(160deg, var(--sky1), var(--sky2)); }
      ha-card::before { content:""; position:absolute; inset:0; z-index:-1; background-image: ${STAR_PATTERN(C.parchment, 0.07)}; }
      .top { display:flex; gap:18px; padding:18px 20px 8px; align-items:flex-start; }
      .hang { display:flex; flex-direction:column; align-items:center; flex:none; }
      .chain { width:1.5px; height:14px; background: ${C.brass}; opacity:.8; }
      .lantern.lit { filter: drop-shadow(0 0 10px rgba(255,181,71,.55)); transform-origin: 50% 0; animation: sway 6s ease-in-out infinite; }
      .lantern .flame { transform-origin: 50% 100%; animation: flicker 2.4s ease-in-out infinite; }
      .lantern .halo { animation: breathe 4s ease-in-out infinite; }
      @keyframes sway { 0%,100% { transform: rotate(-2deg);} 50% { transform: rotate(2deg);} }
      @keyframes flicker { 0%,100% { transform: scaleY(1); opacity:1;} 45% { transform: scaleY(.88); opacity:.9;} 70% { transform: scaleY(1.06);} }
      @keyframes breathe { 0%,100% { opacity:.8;} 50% { opacity:1;} }
      .info { flex:1; min-width:0; padding-top:6px; }
      .lbl { font-size:13px; opacity:.75; }
      .next { display:flex; align-items:baseline; gap:10px; flex-wrap:wrap; margin-top:2px; }
      .next .en { font-size:28px; font-weight:600; letter-spacing:.2px; }
      .next .ar { font-family: ${KUFI}; font-size:22px; color:${C.lamp}; }
      .clock { font-size:40px; font-weight:300; line-height:1.1; margin-top:2px; }
      .rem { font-size:14px; color:${C.lamp}; margin-top:2px; }
      .hijri { font-size:12.5px; opacity:.7; margin-top:8px; }
      .strip { display:grid; grid-template-columns: repeat(var(--n), minmax(0,1fr)); gap:4px; padding:10px 12px 14px; }
      .cell { text-align:center; padding:8px 2px; border-radius:10px; font-size:12.5px; }
      .cell .n { opacity:.75; }
      .cell .v { font-size:14px; margin-top:2px; }
      .cell.past { opacity:.5; }
      .cell.now { background: rgba(255,181,71,.16); box-shadow: inset 0 0 0 1px rgba(255,181,71,.55); }
      .cell.now .n { opacity:1; color:${C.lamp}; }
      .cell.up .v { font-weight:600; }
    `;
  }

  html(m, r) {
    const c = this._config;
    const [s1, s2] = SKY[r.current] || SKY.isha;
    const now = new Date();
    const cells = this.prayers.map((p) => {
      const cls = p === r.current ? "now" : p === r.next ? "up" : m.times[p] < now ? "past" : "";
      return `<div class="cell ${cls}" ${this.attrs(m, p)}><div class="n">${escapeHtml(label(c, p))}</div><div class="v num">${this.t(m.times[p])}</div></div>`;
    }).join("");
    return `<ha-card style="--sky1:${s1};--sky2:${s2};--n:${this.prayers.length}">
      <div class="top">
        <div class="hang"><div class="chain"></div>${lanternSVG("lit", { width: 58, id: "glow" })}</div>
        <div class="info" ${this.attrs(m, r.next)}>
          <div class="lbl">Next prayer</div>
          <div class="next"><span class="en">${escapeHtml(label(c, r.next))}</span>${c.show_arabic ? `<span class="ar" lang="ar">${ARABIC[r.next]}</span>` : ""}</div>
          <div class="clock num">${this.t(r.nextStart)}</div>
          <div class="rem" data-remaining>${formatRemaining(r.remaining)}</div>
          ${c.show_hijri && m.hijri ? `<div class="hijri">${escapeHtml(m.hijri)}</div>` : ""}
        </div>
      </div>
      <div class="strip">${cells}</div>
    </ha-card>`;
  }

  getCardSize() {
    return 5;
  }
}

/* ============================================================ 4. Lantern Night */
class LanternNightCard extends PrayerCardBase {
  static defaults() {
    return { ...super.defaults(), title: "", show_arabic: true };
  }
  static editorSchema = [
    { name: "title", selector: { text: {} } },
    { name: "show_arabic", selector: { boolean: {} } },
    COMMON_SCHEMA(),
  ];

  css() {
    return `
      ha-card { color:${C.parchment}; border:none; position:relative; isolation:isolate;
        background: radial-gradient(120% 90% at 85% 0%, ${C.lapis} 0%, ${C.ink} 62%); }
      .sky { position:absolute; inset:0; z-index:-1; overflow:hidden; }
      .star { position:absolute; width:2px; height:2px; border-radius:50%; background:#fff; opacity:.5; }
      .star.tw { animation: tw 3.5s ease-in-out infinite; }
      @keyframes tw { 0%,100% { opacity:.25;} 50% { opacity:.9;} }
      .moon { position:absolute; right:22px; top:16px; width:30px; height:30px; border-radius:50%;
        box-shadow: 8px -4px 0 0 ${C.parchment}; transform: rotate(-20deg); opacity:.95; }
      .head { display:flex; justify-content:space-between; align-items:baseline; gap:12px; padding:16px 70px 0 18px; }
      .head .t { font-size:15px; opacity:.8; }
      .head .nx { font-size:14px; }
      .head .nx b { color:${C.lamp}; font-weight:600; }
      .garland { position:relative; height:16px; margin: 6px 0 0; }
      .garland svg { position:absolute; inset:0; width:100%; height:24px; overflow:visible; }
      .row { display:grid; grid-template-columns: repeat(var(--n), minmax(0,1fr)); padding: 0 6px 16px; }
      .col { display:flex; flex-direction:column; align-items:center; text-align:center; padding:0 2px; border-radius:12px; }
      .col .cord { width:1px; background:${C.brass}; opacity:.7; }
      .col .lantern { display:block; }
      .col.now .lantern { filter: drop-shadow(0 0 12px rgba(255,181,71,.7)); transform-origin:50% 0; animation: sway 6s ease-in-out infinite; }
      .lantern .flame { transform-origin:50% 100%; animation: flicker 2.4s ease-in-out infinite; }
      @keyframes sway { 0%,100% { transform: rotate(-3deg);} 50% { transform: rotate(3deg);} }
      @keyframes flicker { 0%,100% { transform: scaleY(1);} 45% { transform: scaleY(.86); opacity:.9;} }
      .col .ar { font-family:${KUFI}; font-size:15px; color:${C.lamp}; margin-top:6px; line-height:1.2; }
      .col .n { font-size:13px; margin-top:2px; opacity:.85; }
      .col .v { font-size:15px; font-weight:500; margin-top:2px; }
      .col.past { opacity:.45; }
      .col.now .n { opacity:1; }
      .col.now .v { color:${C.lamp}; }
      .foot { display:flex; justify-content:space-between; gap:8px; padding:0 18px 14px; font-size:12.5px; opacity:.75; }
    `;
  }

  html(m, r) {
    const c = this._config;
    const n = this.prayers.length;
    const now = new Date();
    // Deterministic star field.
    let seed = 7;
    const rnd = () => ((seed = (seed * 9301 + 49297) % 233280) / 233280);
    const stars = Array.from({ length: 28 }, (_, i) =>
      `<i class="star ${i % 4 === 0 ? "tw" : ""}" style="left:${(rnd() * 100).toFixed(1)}%;top:${(rnd() * 46).toFixed(1)}%;animation-delay:${(rnd() * 3).toFixed(2)}s"></i>`
    ).join("");
    // Cord lengths follow the sag of the garland: longer in the middle.
    const cords = this.prayers.map((_, i) => {
      const x = (i + 0.5) / n;
      return Math.round(8 + 22 * Math.sin(Math.PI * x));
    });
    const cols = this.prayers.map((p, i) => {
      const state = p === r.current ? "lit" : m.times[p] < now ? "past" : "idle";
      const cls = p === r.current ? "now" : state === "past" ? "past" : "";
      return `<div class="col ${cls}" ${this.attrs(m, p)}>
        <div class="cord" style="height:${cords[i]}px"></div>
        ${lanternSVG(state, { width: 34, id: "n" + i })}
        ${c.show_arabic ? `<div class="ar" lang="ar">${ARABIC[p]}</div>` : ""}
        <div class="n">${escapeHtml(label(c, p))}</div>
        <div class="v num">${this.t(m.times[p])}</div>
      </div>`;
    }).join("");
    return `<ha-card style="--n:${n}">
      <div class="sky">${stars}<div class="moon"></div></div>
      <div class="head"><span class="t">${escapeHtml(c.title || (c.show_hijri && m.hijri) || "Prayer times")}</span>
        <span class="nx"><b>${escapeHtml(label(c, r.next))}</b> <span data-remaining>${formatRemaining(r.remaining)}</span></span></div>
      <div class="garland"><svg viewBox="0 0 100 24" preserveAspectRatio="none"><path d="M0 2 Q50 46 100 2" fill="none" stroke="${C.brass}" stroke-width="0.6" stroke-dasharray="1.2 1.4" vector-effect="non-scaling-stroke" style="stroke-width:1.4px"/></svg></div>
      <div class="row">${cols}</div>
      ${c.title && c.show_hijri && m.hijri ? `<div class="foot"><span>${escapeHtml(m.hijri)}</span></div>` : ""}
    </ha-card>`;
  }

  getCardSize() {
    return 5;
  }
}

/* ============================================================ 5. Lantern Arch */
class LanternArchCard extends PrayerCardBase {
  static defaults() {
    return { ...super.defaults(), title: "", show_arabic: true };
  }
  static editorSchema = [
    { name: "title", selector: { text: {} } },
    { name: "show_arabic", selector: { boolean: {} } },
    COMMON_SCHEMA(),
  ];

  css() {
    return `
      ha-card { padding:0; position:relative; background: var(--card-background-color); }
      .arch { position:relative; margin:14px 14px 0; padding: 54px 26px 14px 18px; color: var(--primary-text-color); }
      .arch > svg.frame { position:absolute; inset:0; width:100%; height:100%; pointer-events:none; }
      .crest { position:absolute; left:50%; top:10px; transform:translateX(-50%); display:flex; flex-direction:column; align-items:center; }
      .crest .ar { font-family:${KUFI}; color:${C.brassDeep}; font-size:13px; }
      .title { text-align:center; margin-top:4px; }
      .title .h { font-size:15px; font-weight:500; }
      .title .s { font-size:12.5px; color:var(--secondary-text-color); margin-top:2px; }
      ol { list-style:none; margin:14px 0 0; padding:0; position:relative; }
      ol::before { content:""; position:absolute; left:15px; top:10px; bottom:10px; width:2px;
        background: linear-gradient(${C.brass}, ${C.iznik}); opacity:.35; border-radius:1px; }
      li { display:grid; grid-template-columns: 32px 1fr auto; align-items:center; gap:10px; padding:7px 6px 7px 0; border-radius:10px; position:relative; }
      li .mk { display:grid; place-items:center; }
      li .nm { font-size:15px; }
      li .nm .ar { font-family:${KUFI}; color: var(--secondary-text-color); font-size:13px; margin-left:8px; }
      li .tm { font-size:15px; color:var(--secondary-text-color); }
      li.past .nm, li.past .tm { opacity:.55; }
      li.now { background: color-mix(in srgb, ${C.lamp} 14%, transparent); }
      li.now .tm { color: var(--primary-text-color); font-weight:600; }
      li.now .lantern { filter: drop-shadow(0 0 6px rgba(255,181,71,.8)); }
      li .prog { grid-column: 2 / 4; height:3px; border-radius:2px; background: var(--divider-color); overflow:hidden; margin-top:4px; }
      li .prog i { display:block; height:100%; width:var(--p); background:${C.lamp}; }
      .lantern .flame { transform-origin:50% 100%; animation: flicker 2.4s ease-in-out infinite; }
      @keyframes flicker { 0%,100% { transform: scaleY(1);} 45% { transform: scaleY(.86);} }
      .next { display:flex; justify-content:center; gap:12px; padding: 6px 0 16px; font-size:13px; color:var(--secondary-text-color); }
      .next b { color: var(--primary-text-color); font-weight:500; }
    `;
  }

  html(m, r) {
    const c = this._config;
    const now = new Date();
    const items = this.prayers.map((p, i) => {
      const isNow = p === r.current;
      const state = isNow ? "lit" : m.times[p] < now ? "past" : "idle";
      return `<li class="${isNow ? "now" : state === "past" ? "past" : ""}" ${this.attrs(m, p)}>
        <span class="mk">${lanternSVG(state, { width: 16, id: "a" + i })}</span>
        <span class="nm">${escapeHtml(label(c, p))}${c.show_arabic ? `<span class="ar" lang="ar">${ARABIC[p]}</span>` : ""}</span>
        <span class="tm num">${this.t(m.times[p])}</span>
        ${isNow ? `<span class="prog" data-progress style="--p:${(r.progress * 100).toFixed(2)}%"><i></i></span>` : ""}
      </li>`;
    }).join("");
    const lang = (this._hass.locale && this._hass.locale.language) || "en";
    const greg = new Intl.DateTimeFormat(lang, { weekday: "long", day: "numeric", month: "long" }).format(now);
    // Pointed (ogee) arch outline drawn in brass.
    const frame = `<svg class="frame" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
      <path d="M2 100 L2 22 Q2 10 22 6 Q42 3 50 0 Q58 3 78 6 Q98 10 98 22 L98 100" fill="none" stroke="${C.brass}" stroke-width="1.5" vector-effect="non-scaling-stroke"/>
      <path d="M6 100 L6 23 Q6 13 24 9.5 Q42 6.5 50 4 Q58 6.5 76 9.5 Q94 13 94 23 L94 100" fill="none" stroke="${C.brass}" stroke-opacity=".45" stroke-width="1" vector-effect="non-scaling-stroke"/>
    </svg>`;
    return `<ha-card>
      <div class="arch">${frame}
        <div class="crest"><svg width="22" height="22" viewBox="0 0 24 24" aria-hidden="true"><path fill="${C.brass}" d="M12 2l2.6 4.2L19 5l-1.2 4.4L22 12l-4.2 2.6L19 19l-4.4-1.2L12 22l-2.6-4.2L5 19l1.2-4.4L2 12l4.2-2.6L5 5l4.4 1.2z"/><circle cx="12" cy="12" r="3.2" fill="var(--card-background-color)"/></svg></div>
        <div class="title"><div class="h">${escapeHtml(c.title || greg)}</div>
          ${c.show_hijri && m.hijri ? `<div class="s">${escapeHtml(m.hijri)}</div>` : ""}</div>
        <ol>${items}</ol>
      </div>
      <div class="next"><span><b>${escapeHtml(label(c, r.next))}</b> at <span class="num">${this.t(r.nextStart)}</span></span><span data-remaining>${formatRemaining(r.remaining)}</span></div>
    </ha-card>`;
  }

  getCardSize() {
    return 6;
  }
}

/* ---------------------------------------------------------------- shared */
function COMMON_SCHEMA() {
  return {
    type: "expandable",
    name: "",
    title: "Display",
    schema: [
      {
        name: "time_format",
        selector: {
          select: {
            mode: "dropdown",
            options: [
              { value: "auto", label: "Follow Home Assistant" },
              { value: "12", label: "12-hour" },
              { value: "24", label: "24-hour" },
            ],
          },
        },
      },
      { name: "show_ampm", selector: { boolean: {} } },
      { name: "show_sunrise", selector: { boolean: {} } },
      { name: "show_hijri", selector: { boolean: {} } },
      { name: "device", selector: { device: { integration: DOMAIN } } },
    ],
  };
}

const HA_COLORS = {
  primary: "var(--primary-color)", accent: "var(--accent-color)",
  red: "var(--red-color, #f44336)", pink: "var(--pink-color, #e91e63)",
  purple: "var(--purple-color, #926bc7)", "deep-purple": "var(--deep-purple-color, #6e41ab)",
  indigo: "var(--indigo-color, #3f51b5)", blue: "var(--blue-color, #2196f3)",
  "light-blue": "var(--light-blue-color, #03a9f4)", cyan: "var(--cyan-color, #00bcd4)",
  teal: "var(--teal-color, #009688)", green: "var(--green-color, #4caf50)",
  "light-green": "var(--light-green-color, #8bc34a)", lime: "var(--lime-color, #cddc39)",
  yellow: "var(--yellow-color, #ffeb3b)", amber: "var(--amber-color, #ffc107)",
  orange: "var(--orange-color, #ff9800)", "deep-orange": "var(--deep-orange-color, #ff6f22)",
  brown: "var(--brown-color, #795548)", grey: "var(--grey-color, #9e9e9e)",
};
function haColor(c) {
  if (!c) return HA_COLORS.amber;
  return HA_COLORS[c] || c;
}

const FIELD_LABELS = {
  title: "Title", columns: "Columns", accent: "Accent colour", show_arabic: "Show Arabic names",
  time_format: "Time format", show_ampm: "Show AM/PM", show_sunrise: "Show sunrise",
  show_hijri: "Show Hijri date", show_footer: "Show next-prayer footer", device: "Location (if you have several)",
};

/* ------------------------------------------------------------ editor */
class PrayerCardEditor extends HTMLElement {
  setConfig(config) {
    this._config = config;
    this._render();
  }
  set hass(hass) {
    this._hass = hass;
    if (this._form) this._form.hass = hass;
    else this._render();
  }
  _render() {
    if (!this._hass || !this._config) return;
    if (!this._form) {
      this._form = document.createElement("ha-form");
      this._form.computeLabel = (s) => FIELD_LABELS[s.name] || s.title || s.name;
      this._form.addEventListener("value-changed", (ev) => {
        fireEvent(this, "config-changed", { config: ev.detail.value });
      });
      this.appendChild(this._form);
    }
    this._form.hass = this._hass;
    this._form.schema = this.schema || [];
    this._form.data = this._config;
  }
}

/* ------------------------------------------------------------ register */
const CARDS = [
  ["islamic-prayer-times-card", PrayerTimesCard, "Prayer Times: Tiles", "Six tiles with the current prayer highlighted and a countdown to the next."],
  ["islamic-prayer-compact-card", PrayerCompactCard, "Prayer Times: Compact", "One line: the next prayer, its time and how long until it starts."],
  ["islamic-lantern-glow-card", LanternGlowCard, "Prayer Times: Lantern Glow", "A glowing lantern over a sky that follows the time of day, focused on the next prayer."],
  ["islamic-lantern-night-card", LanternNightCard, "Prayer Times: Lantern Night", "Six lanterns on a garland under a night sky – the current prayer's lantern is lit."],
  ["islamic-lantern-arch-card", LanternArchCard, "Prayer Times: Lantern Arch", "A mihrab arch framing a lantern timeline of the day's prayers."],
];

if (!customElements.get("islamic-prayer-card-editor")) {
  customElements.define("islamic-prayer-card-editor", PrayerCardEditor);
}
window.customCards = window.customCards || [];
for (const [tag, cls, name, description] of CARDS) {
  if (!customElements.get(tag)) customElements.define(tag, cls);
  if (!window.customCards.some((c) => c.type === tag)) {
    window.customCards.push({
      type: tag,
      name,
      description,
      preview: true,
      documentationURL: "https://github.com/sariyamon/islamic-prayer-time-ha#cards",
    });
  }
}

console.info(
  `%c ISLAMIC PRAYER TIME %c ${VERSION} `,
  `background:${C.ink};color:${C.lamp};font-weight:700;border-radius:3px 0 0 3px;padding:2px 4px`,
  `background:${C.brass};color:${C.ink};border-radius:0 3px 3px 0;padding:2px 4px`
);
