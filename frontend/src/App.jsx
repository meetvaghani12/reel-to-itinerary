import React, { useEffect, useRef, useState } from "react";
import { s } from "./style.js";
import { extractTrip, fetchRates } from "./api.js";
import {
  STEPS, PIPELINE, QUESTIONS, PLAN_META, PLAN_ORDER, COST_META, COST_KEYS,
  setRates, setCurrency, currencyList, cap, fmt, typeIcon,
} from "./data.js";

const Icon = ({ name, style, cls }) => (
  <span className={"material-symbols-outlined" + (cls ? " " + cls : "")} style={style}>{name}</span>
);

const INITIAL = {
  step: "landing", nextAfterExtract: "places", url: "", tick: 0, data: null,
  qIndex: 0, answers: { style: null, budget: null, group: null, pace: null, party: 3 },
  layout: "cards", selectedPlan: "comfort_traveller", currency: "USD", error: "",
};

// ---- pure helpers over state.data ----
function destinationName(data, url) {
  const ps = (data && data.places) || [];
  for (const x of ps) {
    const loc = x.estimated_location || "";
    if (loc && loc.toLowerCase() !== "unknown") return loc.split(",")[0].trim();
  }
  return data && data.title ? data.title.split(/[|\-–]/)[0].trim().slice(0, 28) : "your destination";
}
function vibesList(data) {
  const out = [];
  const push = (v) => { const c = cap((v || "").trim()); if (c && !out.includes(c)) out.push(c); };
  if (data) push(data.vibe);
  ((data && data.places) || []).forEach((p) => push(p.activity_type));
  return out.slice(0, 6);
}
function recommendedId(answers) {
  if (answers.budget === "low") return "budget_backpacker";
  if (answers.budget === "high") return "luxury_escape";
  return "comfort_traveller";
}
function tripById(data, id) {
  const trips = (data && data.trips) || [];
  return trips.find((t) => t.persona === id) || trips[0];
}
function partyFor(answers) {
  const g = answers.group;
  if (g === "solo") return 1;
  if (g === "couple") return 2;
  if (g === "family" || g === "friends") return Math.max(2, answers.party || 3);
  return 1;
}
function buildPersona(answers) {
  const bmap = { low: ["budget", "low"], mid: ["comfort", "mid"], high: ["luxury", "high"], flex: ["comfort", "mid"] };
  const [travel_style, budget_range] = bmap[answers.budget] || ["comfort", "mid"];
  const pmap = { slow: "relaxed", balanced: "moderate", packed: "packed", surprise: "moderate" };
  return {
    travel_style, budget_range,
    group_type: answers.group || "solo",
    party_size: partyFor(answers),
    pace_preference: pmap[answers.pace] || "moderate",
  };
}

export default function App() {
  const [st, setSt] = useState(INITIAL);
  const ref = useRef(st); ref.current = st;
  const ticker = useRef(null);
  const set = (patch) => setSt((p) => ({ ...p, ...patch }));

  useEffect(() => () => clearInterval(ticker.current), []);

  // Load live FX rates once so the currency selector covers all currencies.
  useEffect(() => {
    fetchRates()
      .then((d) => { setRates(d.rates); set({ ratesReady: true, fxUpdated: d.updated, fxSource: d.source }); })
      .catch(() => set({ ratesReady: true }));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  function startTicker() {
    clearInterval(ticker.current);
    ticker.current = setInterval(() => setSt((p) => ({ ...p, tick: Math.min(p.tick + 1, 44) })), 130);
  }
  function stopTicker() { clearInterval(ticker.current); ticker.current = null; }

  async function runExtract(nextStep) {
    set({ step: "extracting", nextAfterExtract: nextStep, tick: 0 });
    startTicker();
    const started = Date.now();
    try {
      const cur = ref.current;
      const data = await extractTrip(cur.url, buildPersona(cur.answers));
      const elapsed = Date.now() - started;
      if (elapsed < 1600) await new Promise((r) => setTimeout(r, 1600 - elapsed));
      stopTicker();
      if (data.status === "no_places_found" || !data.trips || !data.trips.length) {
        set({ data, step: "noplaces" });
        return;
      }
      const keep = tripById(data, ref.current.selectedPlan) ? ref.current.selectedPlan : data.trips[0].persona;
      set({ data, selectedPlan: keep, step: nextStep });
    } catch (e) {
      stopTicker();
      set({ error: e.message || String(e), step: "error" });
    }
  }

  // ---- handlers ----
  const onExtract = () => {
    if (!st.url.trim()) { set({ url: "https://www.youtube.com/watch?v=uQpiQ4nbM-U" }); }
    setTimeout(() => runExtract("places"), 0);
  };
  const goStep = (key) => {
    if (key === "landing") return restart();
    if (["places", "persona", "plans", "itinerary"].includes(key) && !st.data) return;
    set({ step: key });
  };
  const onAnswer = (val) => {
    const q = QUESTIONS[st.qIndex];
    set({ answers: { ...st.answers, [q.key]: val } });
    // Family/friends reveal a headcount stepper — stay put so the user can set
    // it and press Next. Everything else auto-advances.
    const needsParty = q.key === "group" && (val === "family" || val === "friends");
    if (!needsParty && st.qIndex < QUESTIONS.length - 1) {
      setTimeout(() => set({ qIndex: ref.current.qIndex + 1 }), 240);
    }
  };
  const onQNext = () => {
    if (st.qIndex < QUESTIONS.length - 1) set({ qIndex: st.qIndex + 1 });
    else { set({ selectedPlan: recommendedId(st.answers) }); setTimeout(() => runExtract("plans"), 0); }
  };
  const onQBack = () => { if (st.qIndex === 0) set({ step: "places" }); else set({ qIndex: st.qIndex - 1 }); };
  function restart() { stopTicker(); setCurrency("USD"); setSt(INITIAL); }

  return (
    <div style={{ position: "relative", minHeight: "100vh", background: "#F6F3EC", overflowX: "hidden" }}>
      <div style={s("position:fixed; inset:0; z-index:0; pointer-events:none; background:radial-gradient(ellipse 90% 70% at 78% 88%, rgba(196,98,61,0.10) 0%, rgba(0,0,0,0) 62%)")} />
      <div style={{ position: "relative", zIndex: 1 }}>
        <TopBar st={st} goStep={goStep} restart={restart} set={set} />
        {st.step === "landing" && <Landing st={st} set={set} onExtract={onExtract} />}
        {st.step === "extracting" && <Extracting st={st} />}
        {st.step === "places" && <Places st={st} onToPersona={() => set({ step: "persona", qIndex: 0 })} />}
        {st.step === "persona" && <Persona st={st} set={set} onAnswer={onAnswer} onQNext={onQNext} onQBack={onQBack} />}
        {st.step === "plans" && <Plans st={st} set={set} />}
        {st.step === "itinerary" && <Itinerary st={st} set={set} />}
        {st.step === "noplaces" && <Message title="No places found" icon="explore_off" restart={restart}
          body={(st.data && st.data.message) || "We couldn't find specific travel places in this content. Try a travel vlog or reel that names real places."} />}
        {st.step === "error" && <Message title="Something went wrong" icon="error" restart={restart} body={st.error} />}
      </div>
    </div>
  );
}

// ---------------- Top bar + stepper ----------------
function TopBar({ st, goStep, restart, set }) {
  const curIdx = STEPS.findIndex((x) => x.key === st.step);
  const onCurrency = (e) => { setCurrency(e.target.value); set({ currency: e.target.value }); };
  return (
    <>
      <div style={s("position:sticky; top:0; z-index:40; display:flex; align-items:center; justify-content:space-between; height:66px; padding:0 40px; background:rgba(246,243,236,0.85); backdrop-filter:blur(24px); border-bottom:1px solid rgba(27,26,23,0.08)")}>
        <div style={s("display:flex; align-items:center; gap:14px")}>
          <img src="/assets/devx-labs-wordmark-white.svg" style={{ height: 18, display: "block", filter: "invert(1)" }} alt="devx labs" onError={(e) => (e.currentTarget.style.display = "none")} />
          <span style={s("width:1px; height:20px; background:rgba(27,26,23,0.16)")} />
          <span style={s("font-size:12px; letter-spacing:0.22em; text-transform:uppercase; color:#C4623D; font-weight:500")}>Reel → Itinerary</span>
        </div>
        <div style={s("display:flex; align-items:center; gap:4px")}>
          {STEPS.map((step, i) => {
            const active = step.key === st.step;
            const done = i < curIdx;
            const clickable = step.key === "landing" || (["places", "persona", "plans", "itinerary"].includes(step.key) && st.data);
            const color = active ? "#1B1A17" : done ? "rgba(27,26,23,0.6)" : "rgba(27,26,23,0.38)";
            return (
              <React.Fragment key={step.key}>
                {i > 0 && <span style={{ color: "rgba(27,26,23,0.2)" }}>·</span>}
                <button onClick={() => clickable && goStep(step.key)} disabled={!clickable}
                  style={s(`display:inline-flex; align-items:center; gap:7px; background:${active ? "rgba(196,98,61,0.16)" : "transparent"}; border:1px solid ${active ? "rgba(196,98,61,0.5)" : "transparent"}; color:${color}; padding:7px 13px; font-size:12.5px; font-weight:500; cursor:${clickable ? "pointer" : "default"}; letter-spacing:0.02em; white-space:nowrap`)}>
                  <span style={{ fontVariantNumeric: "tabular-nums", opacity: 0.7 }}>{step.n}</span>{step.label}
                </button>
              </React.Fragment>
            );
          })}
          <select value={st.currency} onChange={onCurrency} title={st.fxUpdated ? `Live rates · ${st.fxUpdated}` : "Display currency"}
            style={s("margin-left:10px; background:rgba(27,26,23,0.05); color:#1B1A17; border:1px solid rgba(27,26,23,0.22); border-radius:999px; padding:8px 12px; font-size:13px; font-weight:500; cursor:pointer; outline:none")}>
            {currencyList().map((c) => (<option key={c} value={c} style={{ background: "#FFFFFF" }}>{c}</option>))}
          </select>
          <button onClick={restart} style={s("margin-left:10px; display:inline-flex; align-items:center; gap:7px; background:transparent; color:rgba(27,26,23,0.72); border:1px solid rgba(27,26,23,0.22); border-radius:999px; padding:8px 16px; font-size:13px; font-weight:500; cursor:pointer")}>
            <Icon name="refresh" style={{ fontSize: 16 }} />Start over
          </button>
        </div>
      </div>
    </>
  );
}

// ---------------- Screen 1: Landing ----------------
function Landing({ st, set, onExtract }) {
  const border = st.url ? "rgba(196,98,61,0.5)" : "rgba(27,26,23,0.14)";
  const samples = [
    { label: "Kerala vlog (YouTube)", icon: "smart_display", color: "#F5585E", url: "https://www.youtube.com/watch?v=uQpiQ4nbM-U" },
    { label: "Bali reel (Instagram)", icon: "photo_camera", color: "#C4623D", url: "https://www.instagram.com/reel/DL0DYF4SL45/" },
  ];
  return (
    <div style={s("max-width:1120px; margin:0 auto; padding:72px 40px 96px; animation:fadeUp .5s ease both")}>
      <div style={s("display:inline-flex; align-items:center; gap:8px; padding:6px 13px; border-radius:999px; background:rgba(196,98,61,0.12); color:#C4623D; font-size:12px; font-weight:500; letter-spacing:0.04em; margin-bottom:34px")}>
        <span style={s("width:6px; height:6px; border-radius:99px; background:#C4623D; animation:pulseDot 2s infinite")} />
        The intelligence layer between saved & booked
      </div>
      <h1 style={s("font-family:'Instrument Serif',serif; font-weight:400; font-size:88px; line-height:0.98; letter-spacing:-0.03em; margin:0; max-width:900px")}>
        Turn a travel reel<br /><em style={{ fontStyle: "italic", color: "#C4623D" }}>into a bookable trip.</em>
      </h1>
      <p style={s("font-size:20px; font-weight:300; line-height:1.55; color:rgba(27,26,23,0.72); margin:32px 0 0; max-width:640px")}>
        Drop a YouTube or Instagram Reel link. We extract every place, activity and vibe, resolve them against real map data, and build personalised itineraries with end-to-end cost estimates.
      </p>
      <div style={s("margin-top:48px; max-width:820px; background:linear-gradient(180deg,rgba(27,26,23,0.02) 0%, rgba(196,98,61,0.10) 100%); backdrop-filter:blur(42px); border:1px solid rgba(27,26,23,0.10); padding:28px")}>
        <div style={s("font-size:12px; letter-spacing:0.25em; text-transform:uppercase; color:#8A8577; font-weight:500; margin-bottom:16px")}>Paste a link</div>
        <div style={s("display:flex; gap:12px; align-items:stretch")}>
          <div style={s(`flex:1; display:flex; align-items:center; gap:12px; background:#FDFBF6; border:1px solid ${border}; padding:0 18px; height:58px`)}>
            <Icon name="link" style={{ fontSize: 22, color: "#C4623D" }} />
            <input value={st.url} onChange={(e) => set({ url: e.target.value })}
              onKeyDown={(e) => e.key === "Enter" && onExtract()}
              placeholder="https://youtube.com/watch?v=…  or  instagram.com/reel/…"
              style={s("flex:1; background:transparent; border:0; outline:none; color:#1B1A17; font-family:inherit; font-size:16px")} />
          </div>
          <button onClick={onExtract} style={s("display:inline-flex; align-items:center; gap:9px; background:#C4623D; color:#fff; border:0; padding:0 28px; font-size:15px; font-weight:600; cursor:pointer; white-space:nowrap")}>
            Extract trip <Icon name="auto_awesome" style={{ fontSize: 20 }} />
          </button>
        </div>
        <div style={s("display:flex; align-items:center; gap:10px; margin-top:16px; flex-wrap:wrap")}>
          <span style={s("font-size:13px; color:#8A8577")}>Try a sample:</span>
          {samples.map((sm) => (
            <button key={sm.url} onClick={() => set({ url: sm.url })} style={s("display:inline-flex; align-items:center; gap:8px; background:rgba(27,26,23,0.04); border:1px solid rgba(27,26,23,0.12); color:rgba(27,26,23,0.85); border-radius:999px; padding:7px 14px; font-size:13px; cursor:pointer")}>
              <Icon name={sm.icon} style={{ fontSize: 16, color: sm.color }} />{sm.label}
            </button>
          ))}
        </div>
      </div>
      <div style={{ marginTop: 56 }}>
        <div style={s("font-size:12px; letter-spacing:0.25em; text-transform:uppercase; color:#8A8577; font-weight:500; margin-bottom:20px")}>How it works</div>
        <div style={s("display:grid; grid-template-columns:repeat(4,1fr); gap:1px; background:rgba(27,26,23,0.08); border:1px solid rgba(27,26,23,0.08)")}>
          {PIPELINE.map((p) => (
            <div key={p.title} style={s("background:#FFFFFF; padding:24px 22px")}>
              <Icon name={p.icon} style={{ fontSize: 26, color: "#C4623D" }} />
              <div style={s("font-size:15px; font-weight:600; margin:14px 0 6px")}>{p.title}</div>
              <div style={s("font-size:13px; line-height:1.5; color:rgba(27,26,23,0.55)")}>{p.body}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ---------------- Screen 2: Extracting ----------------
function Extracting({ st }) {
  const t = st.tick;
  const pct = Math.min(95, Math.round((t / 44) * 100));
  const heading = st.nextAfterExtract === "plans" ? "Tuning your plans" : "Reading the reel";
  const defs = [
    { title: "Fetching transcript & metadata", sub: "Video transcript, description, tags", icon: "download", span: [0, 10] },
    { title: "Extracting places & vibes", sub: "LLM parsing content for named places", icon: "auto_awesome", span: [10, 24] },
    { title: "Resolving with Google Places", sub: "Validating coordinates, category & price tier", icon: "travel_explore", span: [24, 38] },
    { title: "Generating trip plans", sub: "Composing 3 persona-tuned itineraries & costs", icon: "route", span: [38, 44] },
  ];
  return (
    <div style={s("max-width:1180px; margin:0 auto; padding:56px 40px 80px")}>
      <div style={s("display:grid; grid-template-columns:400px 1fr; gap:56px; align-items:start")}>
        <div>
          <div style={s("font-size:12px; letter-spacing:0.25em; text-transform:uppercase; color:#8A8577; font-weight:500; margin-bottom:16px")}>Source</div>
          <div style={s("position:relative; border:1px solid rgba(27,26,23,0.12); background:#FFFFFF; overflow:hidden")}>
            <div style={s("position:relative; aspect-ratio:9/12; background:linear-gradient(150deg,#2A1B12 0%, #3A2418 45%, #1B1310 100%); display:flex; align-items:flex-end; padding:22px")}>
              <div style={s("position:absolute; inset:0; background:radial-gradient(circle at 30% 22%, rgba(196,98,61,0.4), transparent 55%)")} />
              <div style={s("position:absolute; top:0; left:0; right:0; height:2px; background:linear-gradient(90deg,transparent,#E0973B,transparent); animation:scanline 2.4s linear infinite; box-shadow:0 0 12px #E0973B")} />
              <div style={{ position: "relative", zIndex: 2 }}>
                <div style={s("display:inline-flex; align-items:center; gap:6px; background:rgba(0,0,0,0.5); border-radius:999px; padding:4px 10px; font-size:11px; color:#fff; margin-bottom:12px")}><Icon name="play_circle" style={{ fontSize: 14, color: "#F5585E" }} />Analyzing…</div>
                <div style={s("font-family:'Instrument Serif',serif; font-size:26px; line-height:1.05; letter-spacing:-0.02em; color:#fff")}>{(st.data && st.data.title) || "Your travel reel"}</div>
                <div style={s("font-size:14px; color:rgba(255,255,255,0.72); margin-top:4px; word-break:break-all")}>{(st.url || "").slice(0, 60)}</div>
              </div>
              <div style={s("position:absolute; top:18px; right:18px; width:56px; height:56px; border-radius:999px; background:rgba(0,0,0,0.35); backdrop-filter:blur(8px); border:1px solid rgba(27,26,23,0.2); display:flex; align-items:center; justify-content:center; animation:spin 3.5s linear infinite")}><Icon name="travel_explore" style={{ fontSize: 26, color: "#C4623D" }} /></div>
            </div>
            <div style={s("padding:16px 18px; border-top:1px solid rgba(27,26,23,0.08)")}>
              <div style={s("display:flex; gap:10px; font-size:13px; color:rgba(27,26,23,0.65)")}>
                <Icon name="description" style={{ fontSize: 18, color: "#8A8577" }} />
                <span>Transcript · description · captions & location tags parsed</span>
              </div>
            </div>
          </div>
        </div>
        <div style={s("animation:fadeUp .4s ease both")}>
          <div style={s("display:flex; align-items:baseline; justify-content:space-between")}>
            <h2 style={s("font-family:'Instrument Serif',serif; font-weight:400; font-size:48px; line-height:1; letter-spacing:-0.02em; margin:0")}>{heading}<span style={{ color: "#C4623D" }}>…</span></h2>
            <div style={s("font-size:34px; font-weight:300; font-variant-numeric:tabular-nums; color:#C4623D")}>{pct}<span style={{ fontSize: 18 }}>%</span></div>
          </div>
          <div style={s("height:3px; background:rgba(27,26,23,0.1); margin:20px 0 32px; overflow:hidden")}>
            <div style={s(`height:100%; width:${pct}%; background:linear-gradient(90deg,#8A3D22,#C4623D,#E0973B); transition:width .3s linear`)} />
          </div>
          <div style={s("display:flex; flex-direction:column; gap:2px; margin-bottom:36px")}>
            {defs.map((sd) => {
              const state = t >= sd.span[1] ? "done" : t >= sd.span[0] ? "active" : "wait";
              const active = state === "active", done = state === "done";
              return (
                <div key={sd.title} style={s(`display:flex; align-items:center; gap:16px; padding:16px 18px; background:${active ? "rgba(196,98,61,0.10)" : "rgba(27,26,23,0.02)"}; border:1px solid ${active ? "rgba(196,98,61,0.4)" : "rgba(27,26,23,0.07)"}`)}>
                  <span style={s(`width:34px; height:34px; flex:none; display:flex; align-items:center; justify-content:center; background:${done ? "#C4623D" : active ? "rgba(196,98,61,0.2)" : "rgba(27,26,23,0.05)"}`)}>
                    <Icon name={done ? "check" : sd.icon} style={s(`font-size:20px; color:${done ? "#fff" : active ? "#C4623D" : "rgba(27,26,23,0.35)"}; ${active ? "animation:spin 1.4s linear infinite;" : ""}`)} />
                  </span>
                  <div style={{ flex: 1 }}>
                    <div style={s(`font-size:15px; font-weight:600; color:${state === "wait" ? "rgba(27,26,23,0.4)" : "#1B1A17"}`)}>{sd.title}</div>
                    <div style={s("font-size:13px; color:rgba(27,26,23,0.5); margin-top:2px")}>{sd.sub}</div>
                  </div>
                  <span style={s(`font-size:12px; color:${done ? "#C4623D" : active ? "#E0973B" : "rgba(27,26,23,0.3)"}; font-weight:500`)}>{done ? "Done" : active ? "Working…" : "Queued"}</span>
                </div>
              );
            })}
          </div>
          <div style={s("font-size:13px; color:rgba(27,26,23,0.45)")}>Hang tight — a cold extraction runs the LLM + place resolution and can take 10–25s.</div>
        </div>
      </div>
    </div>
  );
}

// ---------------- Screen 3: Places ----------------
function Places({ st, onToPersona }) {
  const places = st.data.places || [];
  const dest = destinationName(st.data, st.url);
  const pos = places.map((_, i) => ({ x: Math.min(86, 18 + ((i * 37) % 64) + (i % 2 ? 4 : 0)), y: Math.min(84, 18 + ((i * 53) % 60)) }));
  const routePoints = pos.map((p) => `${p.x} ${p.y}`).join(" ");
  return (
    <div style={s("max-width:1280px; margin:0 auto; padding:48px 40px 80px; animation:fadeUp .4s ease both")}>
      <div style={s("display:flex; align-items:flex-end; justify-content:space-between; margin-bottom:28px; flex-wrap:wrap; gap:20px")}>
        <div>
          <div style={s("font-size:12px; letter-spacing:0.25em; text-transform:uppercase; color:#8A8577; font-weight:500; margin-bottom:12px")}>Extraction complete · {dest}</div>
          <h2 style={s("font-family:'Instrument Serif',serif; font-weight:400; font-size:56px; line-height:1; letter-spacing:-0.02em; margin:0")}>{places.length} place{places.length === 1 ? "" : "s"} found</h2>
          <p style={s("font-size:16px; color:rgba(27,26,23,0.6); margin:14px 0 0; max-width:560px")}>Extracted from the reel and resolved for category & location. Vibe tags inferred from the transcript & captions.</p>
        </div>
        <button onClick={onToPersona} style={s("display:inline-flex; align-items:center; gap:9px; background:#C4623D; color:#fff; border:0; padding:14px 26px; font-size:15px; font-weight:600; cursor:pointer")}>Build my trip plans<Icon name="arrow_forward" style={{ fontSize: 20 }} /></button>
      </div>
      <div style={s("display:flex; flex-wrap:wrap; gap:10px; margin-bottom:26px")}>
        {vibesList(st.data).map((v) => (
          <span key={v} style={s("display:inline-flex; align-items:center; gap:7px; background:rgba(27,26,23,0.04); border:1px solid rgba(27,26,23,0.12); border-radius:999px; padding:7px 15px; font-size:13px; color:rgba(27,26,23,0.85)")}><span style={s("width:6px; height:6px; border-radius:99px; background:#C4623D")} />{v}</span>
        ))}
      </div>
      <div style={s("display:grid; grid-template-columns:1fr 460px; gap:24px; align-items:start")}>
        <div style={s("position:sticky; top:90px; height:640px; border:1px solid rgba(27,26,23,0.12); background:#FFFFFF; overflow:hidden")}>
          <div style={s("position:absolute; inset:0; background-image:linear-gradient(rgba(196,98,61,0.06) 1px, transparent 1px), linear-gradient(90deg, rgba(196,98,61,0.06) 1px, transparent 1px); background-size:48px 48px")} />
          <div style={s("position:absolute; inset:0; background:radial-gradient(ellipse 60% 50% at 55% 60%, rgba(196,98,61,0.5), transparent 70%); animation:glowPulse 5s ease-in-out infinite")} />
          <svg viewBox="0 0 100 100" preserveAspectRatio="none" style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}>
            <polyline points={routePoints} fill="none" stroke="rgba(196,98,61,0.5)" strokeWidth="0.4" strokeDasharray="1.4 1.2" />
          </svg>
          {places.map((p, i) => (
            <div key={i} style={s(`position:absolute; left:${pos[i].x}%; top:${pos[i].y}%; transform:translate(-50%,-50%); animation:pinPop .4s ease both; animation-delay:${i * 0.06}s`)}>
              <div style={s("display:flex; flex-direction:column; align-items:center; gap:4px")}>
                <div style={s("min-width:26px; height:26px; padding:0 6px; border-radius:999px; background:#C4623D; color:#fff; font-size:13px; font-weight:700; display:flex; align-items:center; justify-content:center; box-shadow:0 0 0 4px rgba(196,98,61,0.25)")}>{i + 1}</div>
                <div style={s("font-size:11px; font-weight:500; color:#1B1A17; background:#FFFFFF; border:1px solid rgba(27,26,23,0.12); padding:2px 7px; white-space:nowrap")}>{p.name}</div>
              </div>
            </div>
          ))}
          <div style={s("position:absolute; left:16px; bottom:16px; display:flex; align-items:center; gap:8px; font-size:11px; letter-spacing:0.18em; text-transform:uppercase; color:rgba(27,26,23,0.5)")}><Icon name="map" style={{ fontSize: 16, color: "#C4623D" }} />{dest} · relative layout</div>
        </div>
        <div style={s("border:1px solid rgba(27,26,23,0.09)")}>
          {places.map((p, i) => {
            const loc = p.estimated_location && p.estimated_location.toLowerCase() !== "unknown" ? p.estimated_location : "LLM extracted";
            return (
              <div key={i} style={s(`display:flex; gap:16px; align-items:center; background:#FFFFFF; padding:16px 18px; ${i ? "border-top:1px solid rgba(27,26,23,0.07);" : ""}`)}>
                <div style={s("width:26px; height:26px; flex:none; border-radius:999px; border:1px solid rgba(196,98,61,0.5); color:#C4623D; font-size:13px; font-weight:700; display:flex; align-items:center; justify-content:center")}>{i + 1}</div>
                <div style={s("width:44px; height:44px; flex:none; background:linear-gradient(150deg,rgba(196,98,61,0.28),rgba(196,98,61,0.12)); display:flex; align-items:center; justify-content:center")}><Icon name={typeIcon(p.type)} style={{ fontSize: 24, color: "#B0552F" }} /></div>
                <div style={s("flex:1; min-width:0")}>
                  <div style={s("font-size:15px; font-weight:600")}>{p.name}</div>
                  <div style={s("font-size:12px; color:rgba(27,26,23,0.5); margin-top:3px; display:flex; align-items:center; gap:8px")}><span>{cap(p.type) || "Place"}</span><span style={{ opacity: 0.4 }}>•</span><span style={{ color: "#B0552F" }}>{loc}</span></div>
                </div>
                <div style={s("font-size:13px; font-weight:600; color:#C4623D")}>{cap(p.activity_type) || ""}</div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

// ---------------- Screen 4: Persona ----------------
function Persona({ st, set, onAnswer, onQNext, onQBack }) {
  const q = QUESTIONS[st.qIndex];
  const answered = st.answers[q.key] != null;
  const isLast = st.qIndex === QUESTIONS.length - 1;
  const showParty = q.key === "group" && ["family", "friends"].includes(st.answers.group);
  const party = Math.max(2, st.answers.party || 3);
  const setParty = (n) => set({ answers: { ...st.answers, party: Math.min(12, Math.max(2, n)) } });
  const stepBtn = "width:38px; height:38px; display:flex; align-items:center; justify-content:center; background:rgba(27,26,23,0.05); border:1px solid rgba(27,26,23,0.14); color:#1B1A17; cursor:pointer; font-size:20px;";
  return (
    <div style={s("max-width:840px; margin:0 auto; padding:64px 40px 80px; animation:fadeUp .4s ease both")}>
      <div style={s("display:flex; align-items:center; justify-content:space-between; margin-bottom:36px")}>
        <div style={s("font-size:12px; letter-spacing:0.25em; text-transform:uppercase; color:#8A8577; font-weight:500")}>Tell us how you travel · Question {st.qIndex + 1} of {QUESTIONS.length}</div>
        <div style={s("display:flex; gap:6px")}>{QUESTIONS.map((_, i) => (<span key={i} style={s(`width:28px; height:4px; background:${i <= st.qIndex ? "#C4623D" : "rgba(27,26,23,0.15)"}`)} />))}</div>
      </div>
      <h2 style={s("font-family:'Instrument Serif',serif; font-weight:400; font-size:52px; line-height:1.02; letter-spacing:-0.02em; margin:0 0 6px")}>{q.title}</h2>
      <p style={s("font-size:16px; color:rgba(27,26,23,0.6); margin:0 0 36px")}>{q.sub}</p>
      <div style={s("display:grid; grid-template-columns:1fr 1fr; gap:14px")}>
        {q.options.map((o) => {
          const sel = st.answers[q.key] === o.val;
          return (
            <button key={o.val} onClick={() => onAnswer(o.val)} style={s(`display:flex; align-items:center; gap:14px; text-align:left; background:${sel ? "rgba(196,98,61,0.10)" : "rgba(27,26,23,0.02)"}; border:1px solid ${sel ? "rgba(196,98,61,0.5)" : "rgba(27,26,23,0.1)"}; padding:16px 18px; cursor:pointer; color:#1B1A17; transition:all .18s ease`)}>
              <span style={s(`width:46px; height:46px; flex:none; background:${sel ? "rgba(196,98,61,0.25)" : "rgba(27,26,23,0.05)"}; display:flex; align-items:center; justify-content:center`)}><Icon name={o.icon} style={{ fontSize: 26, color: sel ? "#C4623D" : "rgba(27,26,23,0.6)" }} /></span>
              <div style={{ textAlign: "left" }}><div style={s("font-size:16px; font-weight:600")}>{o.label}</div><div style={s("font-size:13px; color:rgba(27,26,23,0.55); margin-top:2px")}>{o.hint}</div></div>
              <Icon name="check_circle" style={{ fontSize: 20, color: "#C4623D", marginLeft: "auto", opacity: sel ? 1 : 0, transition: "opacity .2s" }} />
            </button>
          );
        })}
      </div>
      {showParty && (
        <div style={s("display:flex; align-items:center; gap:16px; margin-top:20px; padding:16px 18px; background:rgba(196,98,61,0.08); border:1px solid rgba(196,98,61,0.3)")}>
          <span style={s("font-size:14px; color:rgba(27,26,23,0.85); flex:1")}>How many of you are travelling? <span style={s("color:#8A8577")}>— sets room sharing &amp; per-person cost</span></span>
          <div style={s("display:flex; align-items:center; gap:0")}>
            <button onClick={() => setParty(party - 1)} style={s(stepBtn)}>−</button>
            <span style={s("min-width:48px; text-align:center; font-size:18px; font-weight:700; font-variant-numeric:tabular-nums")}>{party}</span>
            <button onClick={() => setParty(party + 1)} style={s(stepBtn)}>+</button>
          </div>
        </div>
      )}
      <div style={s("display:flex; align-items:center; justify-content:space-between; margin-top:40px")}>
        <button onClick={onQBack} style={s("display:inline-flex; align-items:center; gap:7px; background:transparent; border:1px solid rgba(27,26,23,0.2); color:rgba(27,26,23,0.7); padding:12px 20px; font-size:14px; font-weight:500; cursor:pointer")}><Icon name="arrow_back" style={{ fontSize: 18 }} />Back</button>
        <button onClick={() => answered && onQNext()} disabled={!answered} style={s(`display:inline-flex; align-items:center; gap:8px; background:${answered ? "#C4623D" : "rgba(27,26,23,0.08)"}; color:${answered ? "#fff" : "rgba(27,26,23,0.4)"}; border:0; padding:13px 24px; font-size:14px; font-weight:600; cursor:${answered ? "pointer" : "not-allowed"}`)}>{isLast ? "See my trip plans" : "Next"}<Icon name="arrow_forward" style={{ fontSize: 20 }} /></button>
      </div>
    </div>
  );
}

function planViewModels(data, answers) {
  const recId = recommendedId(answers);
  return PLAN_ORDER.map((id) => {
    const t = tripById(data, id); if (!t) return null;
    const cb = t.cost_breakdown || {};
    const nights = Math.max(1, (t.days || []).length - 1);
    return {
      id, ...PLAN_META[id], isRec: id === recId,
      total: t.total_cost_per_person || COST_KEYS.reduce((a, k) => a + (cb[k] || 0), 0),
      tagline: t.summary || "",
      meta: `${nights} night${nights === 1 ? "" : "s"} · ${(t.days || []).length} days`,
      rows: COST_KEYS.map((k) => ({ label: COST_META[k].label, icon: COST_META[k].icon, v: cb[k] || 0 })),
    };
  }).filter(Boolean);
}

// ---------------- Screen 5: Plans ----------------
function Plans({ st, set }) {
  const dest = destinationName(st.data, st.url);
  const plans = planViewModels(st.data, st.answers);
  const a = st.answers;
  const styleMap = { culture: "culture-led", adventure: "adventure-led", relax: "relaxed", social: "social" };
  const groupMap = { solo: "you", couple: "a couple", friends: "friends", family: "a family" };
  const summary = `Based on a ${styleMap[a.style] || "balanced"} trip for ${groupMap[a.group] || "you"} — we've flagged the closest fit and priced all three end-to-end.`;
  const seg = (on) => `display:inline-flex; align-items:center; gap:6px; background:${on ? "rgba(196,98,61,0.9)" : "transparent"}; color:${on ? "#fff" : "rgba(27,26,23,0.7)"}; border:0; padding:8px 15px; font-size:13px; font-weight:600; cursor:pointer`;
  const cols = `1.2fr ${plans.map(() => "1fr").join(" ")}`;
  return (
    <div style={s("max-width:1280px; margin:0 auto; padding:48px 40px 80px; animation:fadeUp .4s ease both")}>
      <div style={s("display:flex; align-items:flex-end; justify-content:space-between; margin-bottom:12px; flex-wrap:wrap; gap:20px")}>
        <div>
          <div style={s("font-size:12px; letter-spacing:0.25em; text-transform:uppercase; color:#8A8577; font-weight:500; margin-bottom:12px")}>{plans.length} plans · tuned to your persona</div>
          <h2 style={s("font-family:'Instrument Serif',serif; font-weight:400; font-size:56px; line-height:1; letter-spacing:-0.02em; margin:0")}>Your {dest}, three ways</h2>
        </div>
        <div style={s("display:flex; align-items:center; gap:10px")}>
          <span style={s("font-size:12px; color:#8A8577; letter-spacing:0.12em; text-transform:uppercase")}>Layout</span>
          <div style={s("display:flex; background:rgba(27,26,23,0.05); border:1px solid rgba(27,26,23,0.12); padding:3px")}>
            <button onClick={() => set({ layout: "cards" })} style={s(seg(st.layout === "cards"))}><Icon name="view_agenda" style={{ fontSize: 17 }} />Cards</button>
            <button onClick={() => set({ layout: "table" })} style={s(seg(st.layout === "table"))}><Icon name="table_rows" style={{ fontSize: 17 }} />Compare</button>
          </div>
        </div>
      </div>
      <p style={s("font-size:15px; color:rgba(27,26,23,0.55); margin:0 0 32px")}>{summary}</p>

      {st.layout === "cards" ? (
        <div style={s(`display:grid; grid-template-columns:repeat(${plans.length},1fr); gap:20px; align-items:start`)}>
          {plans.map((pl) => (
            <div key={pl.id} style={s(`position:relative; border:1px solid ${pl.isRec ? "rgba(196,98,61,0.6)" : "rgba(27,26,23,0.1)"}; background:linear-gradient(180deg,rgba(27,26,23,0.02),rgba(196,98,61,0.08)); backdrop-filter:blur(42px); ${pl.isRec ? "box-shadow:0 0 0 1px rgba(196,98,61,0.3);" : ""}`)}>
              {pl.isRec && <div style={s("position:absolute; top:0; right:0; background:#C4623D; color:#fff; font-size:11px; font-weight:700; letter-spacing:0.04em; padding:6px 12px")}>Best match for you</div>}
              <div style={s("padding:26px 24px 24px")}>
                <div style={s("display:flex; align-items:center; gap:11px; margin-bottom:18px")}>
                  <span style={s("width:42px; height:42px; background:rgba(196,98,61,0.14); display:flex; align-items:center; justify-content:center")}><Icon name={pl.icon} style={{ fontSize: 24, color: pl.accent }} /></span>
                  <div><div style={s(`font-size:11px; letter-spacing:0.2em; text-transform:uppercase; color:${pl.accent}; font-weight:600`)}>{pl.kicker}</div><div style={s("font-family:'Plus Jakarta Sans','Inter'; font-size:20px; font-weight:700; line-height:1.1")}>{pl.name}</div></div>
                </div>
                <div style={s("font-size:14px; color:rgba(27,26,23,0.6); line-height:1.5; min-height:42px")}>{pl.tagline}</div>
                <div style={s("display:flex; align-items:baseline; gap:8px; margin:22px 0 4px")}><span style={s("font-size:40px; font-weight:300; letter-spacing:-0.02em")}>{fmt(pl.total)}</span><span style={s("font-size:13px; color:#8A8577")}>/ person</span></div>
                <div style={s("font-size:13px; color:rgba(27,26,23,0.5)")}>{pl.meta}</div>
                <div style={s("height:1px; background:rgba(27,26,23,0.1); margin:22px 0")} />
                <div style={s("display:flex; flex-direction:column; gap:11px")}>
                  {pl.rows.map((r) => (
                    <div key={r.label} style={s("display:flex; align-items:center; gap:10px; font-size:13px")}><Icon name={r.icon} style={{ fontSize: 17, color: "#8A8577" }} /><span style={s("flex:1; color:rgba(27,26,23,0.72)")}>{r.label}</span><span style={s("font-variant-numeric:tabular-nums; font-weight:600")}>{fmt(r.v)}</span></div>
                  ))}
                </div>
                <button onClick={() => set({ selectedPlan: pl.id, step: "itinerary" })} style={s(`width:100%; margin-top:22px; display:inline-flex; align-items:center; justify-content:center; gap:8px; background:${pl.isRec ? "#C4623D" : "transparent"}; color:${pl.isRec ? "#fff" : "#1B1A17"}; border:1px solid ${pl.isRec ? "#C4623D" : "rgba(27,26,23,0.25)"}; padding:14px; font-size:14px; font-weight:600; cursor:pointer`)}>View day-by-day<Icon name="arrow_forward" style={{ fontSize: 19 }} /></button>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div style={s("border:1px solid rgba(27,26,23,0.1); overflow:hidden")}>
          <div style={s(`display:grid; grid-template-columns:${cols}`)}>
            <div style={s("background:#FFFFFF; padding:22px 20px; border-bottom:1px solid rgba(27,26,23,0.1)")} />
            {plans.map((pl) => (
              <div key={pl.id} style={s(`background:${pl.isRec ? "rgba(196,98,61,0.12)" : "#FFFFFF"}; padding:22px 20px; border-bottom:1px solid rgba(27,26,23,0.1)`)}>
                <div style={s(`font-size:11px; letter-spacing:0.2em; text-transform:uppercase; color:${pl.accent}; font-weight:600`)}>{pl.kicker}</div>
                <div style={s("font-family:'Plus Jakarta Sans','Inter'; font-size:19px; font-weight:700; margin-top:4px")}>{pl.name}</div>
                <div style={s("font-size:24px; font-weight:300; margin-top:10px")}>{fmt(pl.total)}<span style={s("font-size:12px; color:#8A8577")}> /pp</span></div>
                {pl.isRec && <span style={s("display:inline-block; margin-top:10px; background:#C4623D; color:#fff; font-size:10px; font-weight:700; padding:4px 9px")}>Best match</span>}
              </div>
            ))}
          </div>
          {COST_KEYS.map((k, ri) => (
            <div key={k} style={s(`display:grid; grid-template-columns:${cols}; border-bottom:1px solid rgba(27,26,23,0.07)`)}>
              <div style={s("display:flex; align-items:center; gap:11px; padding:16px 20px; background:#FFFFFF; font-size:14px; color:rgba(27,26,23,0.75)")}><Icon name={COST_META[k].icon} style={{ fontSize: 18, color: "#8A8577" }} />{COST_META[k].label}</div>
              {plans.map((pl, ci) => (<div key={pl.id} style={s(`padding:16px 20px; text-align:right; font-variant-numeric:tabular-nums; font-size:15px; color:rgba(27,26,23,0.85); ${ci === 1 ? "background:rgba(196,98,61,0.05);" : ""}`)}>{fmt(pl.rows[ri].v)}</div>))}
            </div>
          ))}
          <div style={s(`display:grid; grid-template-columns:${cols}; border-top:1px solid rgba(196,98,61,0.4)`)}>
            <div style={s("display:flex; align-items:center; gap:11px; padding:16px 20px; background:#FFFFFF; font-size:14px; color:rgba(27,26,23,0.9); font-weight:600")}><Icon name="functions" style={{ fontSize: 18, color: "#8A8577" }} />Total per person</div>
            {plans.map((pl) => (<div key={pl.id} style={s(`padding:16px 20px; text-align:right; font-variant-numeric:tabular-nums; font-size:15px; font-weight:700; color:${pl.accent}`)}>{fmt(pl.total)}</div>))}
          </div>
          <div style={s(`display:grid; grid-template-columns:${cols}`)}>
            <div style={s("background:#FFFFFF; padding:18px 20px")} />
            {plans.map((pl) => (<div key={pl.id} style={s("padding:16px 18px; text-align:center; background:#FFFFFF")}><button onClick={() => set({ selectedPlan: pl.id, step: "itinerary" })} style={s(`background:${pl.isRec ? "#C4623D" : "transparent"}; color:${pl.isRec ? "#fff" : "#1B1A17"}; border:1px solid ${pl.isRec ? "#C4623D" : "rgba(27,26,23,0.25)"}; padding:11px 18px; font-size:13px; font-weight:600; cursor:pointer`)}>View itinerary</button></div>))}
          </div>
        </div>
      )}
    </div>
  );
}

function toursForTrip(t) {
  const map = {};
  (t.tours || []).forEach((dayT) => (dayT.tours || []).forEach((pt) => { map[(pt.place || "").toLowerCase()] = pt.recommended_tours || []; }));
  return map;
}

// ---------------- Screen 6: Itinerary ----------------
function Itinerary({ st, set }) {
  const t = tripById(st.data, st.selectedPlan);
  if (!t) return <Plans st={st} set={set} />;
  const meta = PLAN_META[t.persona] || PLAN_META.comfort_traveller;
  const dest = destinationName(st.data, st.url);
  const cb = t.cost_breakdown || {};
  const total = t.total_cost_per_person || COST_KEYS.reduce((a, k) => a + (cb[k] || 0), 0);
  const maxRow = Math.max(1, ...COST_KEYS.map((k) => cb[k] || 0));
  const placeType = {}; (st.data.places || []).forEach((p) => (placeType[(p.name || "").toLowerCase()] = p.type));
  const toursMap = toursForTrip(t);
  const times = ["09:00", "11:30", "14:00", "16:30", "19:00", "21:00"];
  return (
    <div style={s("max-width:1280px; margin:0 auto; padding:40px 40px 90px; animation:fadeUp .4s ease both")}>
      <button onClick={() => set({ step: "plans" })} style={s("display:inline-flex; align-items:center; gap:7px; background:transparent; border:0; color:rgba(27,26,23,0.6); font-size:13px; cursor:pointer; margin-bottom:22px")}><Icon name="arrow_back" style={{ fontSize: 18 }} />All plans</button>
      <div style={s("display:flex; align-items:flex-end; justify-content:space-between; flex-wrap:wrap; gap:20px; margin-bottom:8px")}>
        <div>
          <div style={s("display:inline-flex; align-items:center; gap:9px; margin-bottom:14px")}>
            <span style={s("width:38px; height:38px; background:rgba(196,98,61,0.16); display:flex; align-items:center; justify-content:center")}><Icon name={meta.icon} style={{ fontSize: 22, color: meta.accent }} /></span>
            <span style={s(`font-size:11px; letter-spacing:0.22em; text-transform:uppercase; color:${meta.accent}; font-weight:600`)}>{meta.kicker} itinerary</span>
          </div>
          <h2 style={s("font-family:'Instrument Serif',serif; font-weight:400; font-size:52px; line-height:1.04; letter-spacing:-0.02em; margin:0")}>{t.title || meta.name}</h2>
          <p style={s("font-size:15px; color:rgba(27,26,23,0.6); margin:16px 0 0")}>{dest} · {(t.days || []).length} days</p>
        </div>
        <div style={s("display:flex; background:rgba(27,26,23,0.05); border:1px solid rgba(27,26,23,0.12); padding:3px")}>
          {PLAN_ORDER.filter((id) => tripById(st.data, id)).map((id) => {
            const on = id === st.selectedPlan;
            return <button key={id} onClick={() => set({ selectedPlan: id })} style={s(`background:${on ? "rgba(196,98,61,0.9)" : "transparent"}; color:${on ? "#fff" : "rgba(27,26,23,0.7)"}; border:0; padding:9px 18px; font-size:13px; font-weight:600; cursor:pointer`)}>{PLAN_META[id].kicker}</button>;
          })}
        </div>
      </div>
      <div style={s("display:grid; grid-template-columns:1fr 380px; gap:32px; align-items:start; margin-top:36px")}>
        <div style={s("display:flex; flex-direction:column; gap:22px")}>
          {(t.days || []).map((d) => (
            <div key={d.day} style={s("border:1px solid rgba(27,26,23,0.1); background:linear-gradient(180deg,rgba(27,26,23,0.015),rgba(196,98,61,0.05))")}>
              <div style={s("display:flex; align-items:center; gap:14px; padding:18px 22px; border-bottom:1px solid rgba(27,26,23,0.08)")}>
                <span style={s("font-family:'Instrument Serif',serif; font-size:34px; line-height:1; color:#C4623D")}>{String(d.day).padStart(2, "0")}</span>
                <div><div style={s("font-size:11px; letter-spacing:0.2em; text-transform:uppercase; color:#8A8577")}>Day {d.day}{d.region ? " · " + d.region : ""}</div><div style={s("font-family:'Plus Jakarta Sans','Inter'; font-size:19px; font-weight:700")}>{d.theme || "Explore"}</div></div>
              </div>
              <div style={s("padding:8px 22px 20px")}>
                {(d.stops || []).map((stop, si) => {
                  const recs = toursMap[(stop.place_name || "").toLowerCase()] || [];
                  return (
                    <div key={si} style={s("display:flex; gap:18px; padding:16px 0; border-bottom:1px solid rgba(27,26,23,0.06)")}>
                      <div style={s("width:56px; flex:none; font-size:13px; font-weight:600; color:#B0552F; font-variant-numeric:tabular-nums; padding-top:2px")}>{times[si] || ""}</div>
                      <div style={s("flex:1; min-width:0")}>
                        <div style={s("display:flex; align-items:center; gap:9px; flex-wrap:wrap")}>
                          <Icon name={typeIcon(placeType[(stop.place_name || "").toLowerCase()])} style={{ fontSize: 19, color: "#C4623D" }} />
                          <span style={s("font-size:16px; font-weight:600")}>{stop.place_name}</span>
                          <span style={s("font-size:12px; color:#8A8577")}>· {stop.duration || stop.activity || ""}</span>
                        </div>
                        <div style={s("font-size:13px; color:rgba(27,26,23,0.55); margin:5px 0 0 28px; line-height:1.5")}>{stop.description || stop.activity || ""}</div>
                        {recs.length > 0 && (
                          <div style={s("display:flex; flex-direction:column; gap:8px; margin:12px 0 0 28px")}>
                            {recs.map((tr, ti) => {
                              const price = tr.price && typeof tr.price === "object" ? tr.price.amount : tr.price;
                              const dur = tr.duration && typeof tr.duration === "object" ? tr.duration.formatted : tr.duration;
                              const prov = (tr.tags && tr.tags[0]) || tr.category || "Tour";
                              return (
                                <div key={ti} style={s("display:flex; align-items:center; gap:12px; background:rgba(196,98,61,0.08); border:1px solid rgba(196,98,61,0.22); padding:10px 12px")}>
                                  <Icon name="confirmation_number" style={{ fontSize: 18, color: "#C4623D" }} />
                                  <div style={s("flex:1; min-width:0")}><div style={s("font-size:13px; font-weight:600")}>{tr.title || "Tour"}</div><div style={s("font-size:11px; color:#8A8577; margin-top:2px")}>{cap(prov)} · matched to {meta.name}</div></div>
                                  <div style={s("text-align:right; white-space:nowrap")}><div style={s("font-size:14px; font-weight:700; color:#B0552F")}>{price ? fmt(price) : "—"}</div><div style={s("font-size:11px; color:#8A8577")}>{dur || ""}</div></div>
                                </div>
                              );
                            })}
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
        <div style={s("position:sticky; top:90px; display:flex; flex-direction:column; gap:20px")}>
          <div style={s("border:1px solid rgba(27,26,23,0.1); background:linear-gradient(180deg,rgba(27,26,23,0.02),rgba(196,98,61,0.09)); backdrop-filter:blur(42px); padding:24px")}>
            <div style={s("font-size:12px; letter-spacing:0.25em; text-transform:uppercase; color:#8A8577; font-weight:500; margin-bottom:18px")}>Cost breakdown · per person</div>
            <div style={s("display:flex; flex-direction:column; gap:14px")}>
              {COST_KEYS.map((k) => {
                const v = cb[k] || 0;
                return (
                  <div key={k}>
                    <div style={s("display:flex; align-items:center; gap:10px; font-size:14px; margin-bottom:6px")}><Icon name={COST_META[k].icon} style={{ fontSize: 18, color: "#8A8577" }} /><span style={s("flex:1; color:rgba(27,26,23,0.78)")}>{COST_META[k].label}</span><span style={s("font-weight:600; font-variant-numeric:tabular-nums")}>{fmt(v)}</span></div>
                    <div style={s("height:4px; background:rgba(27,26,23,0.07)")}><div style={s(`height:100%; width:${Math.round((v / maxRow) * 100)}%; background:${meta.accent}`)} /></div>
                  </div>
                );
              })}
            </div>
            <div style={s("height:1px; background:rgba(27,26,23,0.12); margin:20px 0")} />
            <div style={s("display:flex; align-items:baseline; justify-content:space-between")}><span style={s("font-size:15px; color:rgba(27,26,23,0.8)")}>Total / person</span><span style={s(`font-size:34px; font-weight:300; letter-spacing:-0.02em; color:${meta.accent}`)}>{fmt(total)}</span></div>
            <button onClick={() => alert("Booking hand-off would happen here — out of scope for the assignment.")} style={s("width:100%; margin-top:20px; display:inline-flex; align-items:center; justify-content:center; gap:9px; background:#C4623D; color:#fff; border:0; padding:15px; font-size:15px; font-weight:600; cursor:pointer")}>Book this trip<Icon name="arrow_forward" style={{ fontSize: 20 }} /></button>
            <div style={s("text-align:center; font-size:12px; color:#8A8577; margin-top:12px")}>Flights indicative · costs computed deterministically</div>
          </div>
          <div style={s("border:1px solid rgba(27,26,23,0.1); background:#FFFFFF; padding:20px")}>
            <div style={s("display:flex; align-items:center; gap:9px; font-size:13px; color:rgba(27,26,23,0.6)")}><Icon name="insights" style={{ fontSize: 18, color: "#C4623D" }} />Matched from your reel</div>
            <div style={s("font-size:13px; color:rgba(27,26,23,0.5); line-height:1.55; margin-top:10px")}>{t.summary || "Every stop comes from the places extracted from your reel, sequenced by region and priced for your persona."}</div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ---------------- Message (no-places / error) ----------------
function Message({ title, body, icon, restart }) {
  return (
    <div style={s("max-width:720px; margin:0 auto; padding:120px 40px; text-align:center; animation:fadeUp .4s ease both")}>
      <Icon name={icon} style={{ fontSize: 54, color: "#C4623D" }} />
      <h2 style={s("font-family:'Instrument Serif',serif; font-weight:400; font-size:48px; margin:18px 0 10px; letter-spacing:-0.02em")}>{title}</h2>
      <p style={s("font-size:16px; color:rgba(27,26,23,0.65); line-height:1.6; margin:0 auto 30px; max-width:520px")}>{body}</p>
      <button onClick={restart} style={s("display:inline-flex; align-items:center; gap:9px; background:#C4623D; color:#fff; border:0; padding:14px 26px; font-size:15px; font-weight:600; cursor:pointer")}><Icon name="arrow_back" style={{ fontSize: 20 }} />Try another link</button>
    </div>
  );
}
