"use client";

import { useEffect, useMemo, useState } from "react";
import Image from "next/image";
import { useLanguage } from "./SiteShell";
import type { EpisodeBundle, ReleaseProfile } from "../lib/types";
import "./console.css";
import "./recorded.css";

type Manifest={default_candidate_id:string;profiles:Array<{candidate_id:string;href:string}>;replays:Array<{replay_id:string;candidate_id:string;policy:string;route_mode:string;repair_success:boolean;href:string}>};

export function EvidenceConsole(){
  const {language}=useLanguage(); const zh=language==="zh";
  const tx=(en:string,cn:string)=>zh?cn:en;
  const [manifest,setManifest]=useState<Manifest|null>(null); const [candidateId,setCandidateId]=useState(""); const [profile,setProfile]=useState<ReleaseProfile|null>(null); const [bundle,setBundle]=useState<EpisodeBundle|null>(null);
  const [replayId,setReplayId]=useState(""); const [cursor,setCursor]=useState(0); const [playing,setPlaying]=useState(false); const [sensorMode,setSensorMode]=useState<"rgb"|"depth"|"mask">("rgb");
  useEffect(()=>{fetch("/data/manifest.json").then(r=>r.json()).then((m:Manifest)=>{setManifest(m);setCandidateId(m.default_candidate_id)})},[]);
  useEffect(()=>{if(!manifest||!candidateId)return;const href=manifest.profiles.find(p=>p.candidate_id===candidateId)?.href;if(href)fetch(href).then(r=>r.json()).then((p:ReleaseProfile)=>{setProfile(p);setReplayId(p.default_replays[0]||"")})},[manifest,candidateId]);
  useEffect(()=>{const row=manifest?.replays.find(r=>r.replay_id===replayId);if(row)fetch(row.href).then(r=>r.json()).then((b:EpisodeBundle)=>{setBundle(b);setCursor(0);setPlaying(false)})},[manifest,replayId]);
  useEffect(()=>{if(!playing||!bundle)return;const timer=setInterval(()=>setCursor(c=>c>=bundle.events.length-1?(setPlaying(false),c):c+1),850);return()=>clearInterval(timer)},[playing,bundle]);
  const event=bundle?.events[cursor];
  const visibleEvents=useMemo(()=>bundle?.events.slice(0,cursor+1)||[],[bundle,cursor]);
  const frame=useMemo(()=>{if(!bundle)return undefined;const seen=visibleEvents.filter(e=>e.type==="observation").at(-1);return bundle.sensor_frames.find(f=>f.frame_id===seen?.ref_id)||bundle.sensor_frames[0]},[bundle,visibleEvents]);
  const gate=useMemo(()=>{if(!bundle)return undefined;const seen=visibleEvents.filter(e=>e.type==="gate_decision").at(-1);return bundle.gate_receipts.find(g=>g.receipt_sha256===seen?.ref_id)||bundle.gate_receipts[0]},[bundle,visibleEvents]);
  if(!manifest||!profile||!bundle)return <div className="loading">LOADING EVIDENCE PACK…</div>;
  return <main className="console-wrap">
    <div className="console-toolbar">
      <label><span>{tx("ACTIVE CANDIDATE","当前候选")}</span><select aria-label="Candidate" value={candidateId} onChange={e=>setCandidateId(e.target.value)}>{manifest.profiles.map(p=><option key={p.candidate_id} value={p.candidate_id}>{p.candidate_id.toUpperCase()}</option>)}</select></label>
      <label><span>{tx("REPLAY","证据回放")}</span><select aria-label="Replay" value={replayId} onChange={e=>setReplayId(e.target.value)}>{manifest.replays.filter(r=>r.candidate_id===candidateId).map(r=><option key={r.replay_id} value={r.replay_id}>{r.policy.includes("active")?tx("ACTIVE · REPAIR → DIRECT","主动 · 修证 → 直行"):tx("PASSIVE · DENY → DETOUR","被动 · 拒绝 → 绕行")}</option>)}</select></label>
      <div className="evidence-labels"><span>RECORDED AMD GPU EVIDENCE REPLAY</span><span>SIMULATION ONLY</span><span>FROZEN ARTIFACT</span></div>
    </div>
    <div className="console-grid">
      <section className="sensor-panel console-panel">
        <PanelHead title={tx("SENSOR EVIDENCE","传感器证据")} value={`${frame?.corridor_id||"—"} / ${frame?.viewpoint||"—"}`} />
        <div className="sensor-tabs">{(["rgb","depth","mask"] as const).map(m=><button className={sensorMode===m?"active":""} key={m} onClick={()=>setSensorMode(m)}>{m==="mask"?"CORRIDOR MASK":m.toUpperCase()}</button>)}</div>
        <div className={`sensor-viewport ${sensorMode}`}>
          {frame?.media.available ? <Image fill unoptimized className="recorded-frame" src={frame.media[sensorMode==="mask"?"corridor_mask":sensorMode]} alt={`${sensorMode} evidence at ${frame.viewpoint}`}/> : <div className="sensor-scene"><div className="scene-rack left"/><div className="scene-rack right"/><div className="scene-path"/><div className="scene-obstacle"/><div className="scene-mask"/></div>}
          <div className="recorded-overlay"><span>FRAME {frame?.frame_id?.replace("frame-","").padStart(2,"0")}</span><span>{frame?.tensor_device}</span></div>
          <div className="media-note">{frame?.media.available?(zh?"AMD GPU 记录帧 · SHA 已归档":"Recorded AMD GPU frame · SHA archived"):(zh?"原始帧哈希已归档；显示证据示意层":"Raw frame hash archived · evidence geometry view")}</div>
        </div>
        <div className="sensor-stats"><Metric label="P(BLOCKED)" value={formatP(frame?.p_blocked)}/><Metric label={tx("PREDICTION SET","预测集")} value={`{${frame?.prediction_set?.join(", ")||"—"}}`}/><Metric label="CLAIM" value={(frame?.value||"—").toUpperCase()} accent/></div>
      </section>
      <section className="gate-panel console-panel">
        <PanelHead title={tx("ACTION QUALIFICATION","动作资格审查")} value={`${tx("STEP","步骤")} ${event?.step||0}`} />
        <div className="gate-stack">
          <GateRow label={tx("PYTHON CONTRACT","PYTHON 合同")} pass={!!gate?.python_admitted}/><GateRow label="PURIFY GO GATE" pass={!!gate?.purify_go_admitted}/><GateRow label={tx("EFFECTIVE ADMIT","最终准入")} pass={!!gate?.effective_admit} major/>
        </div>
        <div className="contract-list">
          <span>{tx("ACTION CONTRACT","动作合同")}</span>
          <Clause label={tx("Fresh calibrated evidence","证据新鲜且校准适用")} pass={!gate?.belief_gaps?.includes("stale")}/>
          <Clause label={tx("Independent side-view root","独立侧视采集根")} pass={!gate?.reasons?.includes("missing_side_view_vision_root")}/>
          <Clause label={tx("No unresolved conflict","无未解决冲突")} pass={!gate?.reasons?.some(r=>r.includes("conflict"))}/>
          <Clause label={tx("Python ∧ Purify authorization","Python ∧ Purify 双重授权")} pass={!!gate?.effective_admit}/>
        </div>
        <div className="root-map"><span>{tx("PHYSICAL MEASUREMENT ROOTS","物理测量根")}</span><div>{bundle.measurement_roots.map((r,i)=><i key={r.measurement_root_id} className={r.observed_step<=(event?.step||0)?"used":""} title={r.measurement_root_id}>{i+1}</i>)}</div></div>
      </section>
      <section className="decision-panel console-panel">
        <PanelHead title={tx("ROBOT DECISION","机器人决策")} value={event?.type?.replaceAll("_"," ").toUpperCase()||"—"}/>
        <div className={`decision-state ${gate?.effective_admit?"admit":"deny"}`}><span>{tx("CURRENT AUTHORIZATION","当前授权")}</span><strong>{gate?.effective_admit?tx("ADMITTED","准入"):tx("DENIED","拒绝")}</strong><p>{gate?.effective_admit?(zh?"证据合同满足，可直接通行。":"Evidence contract satisfied. Direct action qualified."):(zh?"动作未获授权；获取新证据或安全绕行。":"Action not qualified. Acquire evidence or take a safe detour.")}</p></div>
        <div className="nbv-card"><span>{tx("NEXT-BEST VIEW","下一最佳视角")}</span><b>{bundle.repair_requests.length?String(bundle.repair_requests[0].target_viewpoint||"side view").replaceAll("_"," ").toUpperCase():tx("NOT REQUESTED","未请求")}</b><small>{bundle.repair_requests.length?tx("NEW CAPTURE ROOT · TARGETED REPAIR","新采集根 · 定向修证"):tx("PASSIVE POLICY · FAIL CLOSED","被动策略 · 安全拒绝")}</small></div>
        <div className="outcome-row"><span>{tx("FINAL ROUTE","最终路线")}</span><b className={bundle.outcome.route_mode}>{bundle.outcome.route_mode.toUpperCase()}</b><span>{tx("UNSAFE","不安全事件")}</span><b className="safe">{bundle.outcome.unsafe_crossing?tx("YES","是"):"0"}</b></div>
      </section>
    </div>
    <section className="timeline-panel">
      <div className="playback"><button onClick={()=>setCursor(Math.max(0,cursor-1))}>‹</button><button className="play" onClick={()=>setPlaying(!playing)}>{playing?"Ⅱ":"▶"}</button><button onClick={()=>setCursor(Math.min(bundle.events.length-1,cursor+1))}>›</button><span>{String(cursor+1).padStart(2,"0")} / {String(bundle.events.length).padStart(2,"0")}</span></div>
      <div className="timeline">{bundle.events.map((e,i)=><button key={e.event_id} title={`${e.type} · ${e.status}`} className={`${e.type} ${i<=cursor?"seen":""} ${i===cursor?"current":""}`} onClick={()=>setCursor(i)}><i/><span>{e.step}</span></button>)}</div>
      <a className="raw-link" href={`/data/replays/${replayId}.json`} target="_blank">RAW JSON ↗</a>
    </section>
    <div className="integrity-bar"><span>SOURCE EPISODE <b>{bundle.integrity.source_episode_sha256.slice(0,16)}…</b></span><span>BUNDLE <b>{bundle.integrity.bundle_sha256.slice(0,16)}…</b></span><span>LIVE GPU DEPENDENCY <b>NONE</b></span></div>
  </main>;
}

function PanelHead({title,value}:{title:string;value:string}){return <div className="panel-head"><b>{title}</b><span>{value}</span></div>}
function Metric({label,value,accent}:{label:string;value:string;accent?:boolean}){return <div><span>{label}</span><b className={accent?"accent":""}>{value}</b></div>}
function GateRow({label,pass,major}:{label:string;pass:boolean;major?:boolean}){return <div className={major?"major":""}><span>{label}</span><b className={pass?"pass":"fail"}>{pass?"ADMIT":"DENY"}</b></div>}
function Clause({label,pass}:{label:string;pass:boolean}){return <div><i className={pass?"pass":"fail"}>{pass?"✓":"×"}</i><span>{label}</span><b>{pass?"PASS":"OPEN"}</b></div>}
function formatP(value?:number){if(value===undefined)return "—";if(value<.001)return value.toExponential(1);return value.toFixed(3)}
