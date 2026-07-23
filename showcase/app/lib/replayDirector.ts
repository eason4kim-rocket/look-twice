import type {
  EpisodeBundle,
  GateReceiptV11,
  MotionSegment,
  ReplayEvent,
} from "./types";
import { routeBeforeAction } from "./replayTimeline";

export type ReplayChapterKind =
  | "observe"
  | "deny"
  | "plan"
  | "move"
  | "repair"
  | "act";

export type ReplayChapter = {
  id: string;
  kind: ReplayChapterKind;
  label: string;
  title: string;
  body: string;
  eventIndex: number;
  frameIds: string[];
  gateId?: string;
  requestId?: string;
  motionIds: string[];
};

export type ChapterState = {
  event?: ReplayEvent;
  gate?: GateReceiptV11;
  motion?: MotionSegment;
  frameIds: string[];
  routeMode: string;
  revealOutcome: boolean;
};

function eventIndex(
  bundle: EpisodeBundle,
  predicate: (event: ReplayEvent) => boolean,
) {
  return bundle.events.findIndex(predicate);
}

function gateForEvent(bundle: EpisodeBundle, event?: ReplayEvent) {
  if (!event || event.ref_kind !== "gate_receipt") return undefined;
  return bundle.gate_receipts.find((gate) => gate.gate_id === event.ref_id);
}

export function buildReplayChapters(
  bundle: EpisodeBundle,
  zh = false,
): ReplayChapter[] {
  const selected = bundle.outcome.selected_corridor;
  const observations = bundle.events
    .map((event, index) => ({ event, index }))
    .filter(({ event }) => event.type === "observation");
  const initialObservation =
    observations.find(({ event }) => {
      const frame = bundle.sensor_frames.find(
        (candidate) => candidate.frame_id === event.ref_id,
      );
      return frame?.corridor_id === selected;
    }) || observations[0];
  const gateEvents = bundle.events
    .map((event, index) => ({ event, index, gate: gateForEvent(bundle, event) }))
    .filter(({ gate }) => Boolean(gate));
  const firstDeny =
    gateEvents.find(
      ({ gate }) => gate?.corridor_id === selected && !gate.effective_admit,
    ) || gateEvents.find(({ gate }) => !gate?.effective_admit);
  const admit = gateEvents.find(
    ({ gate }) => gate?.corridor_id === selected && gate.effective_admit,
  );
  const requests = bundle.repair_requests.filter(
    (request) =>
      request.authorized &&
      (request.target_scope as { region_id?: string } | undefined)?.region_id ===
        selected,
  );
  const selectedRequest =
    requests.at(-1) ||
    bundle.repair_requests.find((request) => request.authorized);
  const requestIndex = selectedRequest
    ? eventIndex(
        bundle,
        (event) =>
          event.ref_kind === "repair_request" &&
          event.ref_id === selectedRequest.request_id,
      )
    : -1;
  const repairMotionId = String(selectedRequest?.motion_id || "");
  const moveIndex = repairMotionId
    ? eventIndex(
        bundle,
        (event) =>
          event.ref_kind === "motion_segment" &&
          event.ref_id === repairMotionId,
      )
    : -1;
  const repairFrames = observations
    .filter(({ event }) => {
      const frame = bundle.sensor_frames.find(
        (candidate) => candidate.frame_id === event.ref_id,
      );
      return (
        frame?.corridor_id === selected &&
        event.step > (firstDeny?.event.step || -1)
      );
    })
    .map(({ event }) => event.ref_id);
  const actionMotion = bundle.motion_segments.find((motion) =>
    ["direct_cross", "safe_detour"].includes(motion.purpose),
  );
  const outcomeIndex = eventIndex(bundle, (event) => event.type === "outcome");
  const active = bundle.outcome.repair_attempted;
  const chapters: ReplayChapter[] = [
    {
      id: "observe",
      kind: "observe",
      label: zh ? "观察" : "OBSERVE",
      title: zh ? "视觉判断走廊畅通" : "Vision says the corridor is clear",
      body: zh
        ? "但一张主车前视快照不足以授权物理动作；这不是连续车载视频。"
        : "But one carrier-front snapshot is not enough to authorize physical action; this is not continuous onboard video.",
      eventIndex: Math.max(0, initialObservation?.index || 0),
      frameIds: initialObservation ? [initialObservation.event.ref_id] : [],
      motionIds: [],
    },
    {
      id: "deny",
      kind: "deny",
      label: zh ? "拒绝" : "DENY",
      title: zh ? "Purify 阻止未经证据支持的动作" : "Purify stops the unsupported action",
      body: zh
        ? "这不是在声明存在遮挡。动作合同要求第二个独立采集根，同源快照不能替代独立复核。"
        : "This is not an occlusion finding. The action contract requires a second independent capture root.",
      eventIndex: Math.max(0, firstDeny?.index || 0),
      frameIds: initialObservation ? [initialObservation.event.ref_id] : [],
      gateId: firstDeny?.gate?.gate_id,
      motionIds: [],
    },
  ];
  if (active) {
    chapters.push(
      {
        id: "plan",
        kind: "plan",
        label: zh ? "规划" : "PLAN",
        title: zh ? "BeliefGap 指出缺少的证据" : "The BeliefGap identifies what is missing",
        body: zh
          ? "NBV 选择独立复核视角来修复合同缺口，而不是盲目重拍。"
          : "NBV selects an independent verification viewpoint to repair the contract—not a blind retry.",
        eventIndex: Math.max(0, requestIndex),
        frameIds: initialObservation ? [initialObservation.event.ref_id] : [],
        gateId: firstDeny?.gate?.gate_id,
        requestId: String(selectedRequest?.request_id || ""),
        motionIds: repairMotionId ? [repairMotionId] : [],
      },
      {
        id: "move",
        kind: "move",
        label: zh ? "移动" : "MOVE",
        title: zh
          ? "侦察车移动到独立复核视角"
          : "The scout moves to an independent verification view",
        body: zh
          ? "移动期间右侧仍显示 ROOT 01 静态快照；侦察车到位后才采集 ROOT 02。"
          : "During motion, the panel still shows static ROOT 01. ROOT 02 is captured only after the scout arrives.",
        eventIndex: Math.max(0, moveIndex),
        frameIds: initialObservation ? [initialObservation.event.ref_id] : [],
        gateId: firstDeny?.gate?.gate_id,
        requestId: String(selectedRequest?.request_id || ""),
        motionIds: repairMotionId ? [repairMotionId] : [],
      },
      {
        id: "repair",
        kind: "repair",
        label: zh ? "修复" : "REPAIR",
        title: zh ? "独立证据修复了动作合同" : "Independent evidence repairs the contract",
        body: zh
          ? "ROOT 01 → ROOT 02：第二个独立采集根加入后，Purify 重新评估，Python 与 Purify Go 同时准入。"
          : "ROOT 01 → ROOT 02: after the second independent root arrives, Purify reevaluates and both gates admit.",
        eventIndex: Math.max(0, admit?.index || outcomeIndex),
        frameIds: [
          ...(initialObservation ? [initialObservation.event.ref_id] : []),
          ...(repairFrames.length ? [repairFrames.at(-1)!] : []),
        ],
        gateId: admit?.gate?.gate_id,
        requestId: String(selectedRequest?.request_id || ""),
        motionIds: repairMotionId ? [repairMotionId] : [],
      },
    );
  }
  chapters.push({
    id: "act",
    kind: "act",
    label: zh ? "行动" : "ACT",
    title:
      bundle.outcome.route_mode === "direct"
        ? zh
          ? "动作获得授权，机器人安全直行"
          : "The qualified robot action crosses directly"
        : zh
          ? "证据未修复，机器人安全绕行"
          : "The evidence remains unqualified, so the robot detours",
    body:
      bundle.outcome.route_mode === "direct"
        ? zh
          ? "最终路线为直行，未发生不安全穿越。更好的证据改变了动作资格。"
          : "Final route: DIRECT, unsafe=0. Better evidence changed action qualification."
        : zh
          ? "被动策略保持安全，但为不确定性付出绕行代价。"
          : "The passive policy stays safe, but pays for uncertainty with a detour.",
    eventIndex: Math.max(0, outcomeIndex),
    frameIds: repairFrames.length
      ? [repairFrames.at(-1)!]
      : initialObservation
        ? [initialObservation.event.ref_id]
        : [],
    gateId: admit?.gate?.gate_id || firstDeny?.gate?.gate_id,
    motionIds: actionMotion ? [actionMotion.motion_id] : [],
  });
  return chapters;
}

export function resolveChapterState(
  bundle: EpisodeBundle,
  chapter: ReplayChapter,
): ChapterState {
  const event = bundle.events[chapter.eventIndex];
  const gate = chapter.gateId
    ? bundle.gate_receipts.find((candidate) => candidate.gate_id === chapter.gateId)
    : undefined;
  const motion = chapter.motionIds.length
    ? bundle.motion_segments.find(
        (candidate) => candidate.motion_id === chapter.motionIds[0],
      )
    : undefined;
  const revealOutcome = chapter.kind === "act";
  return {
    event,
    gate,
    motion,
    frameIds: chapter.frameIds,
    routeMode: routeBeforeAction(bundle.outcome.route_mode, revealOutcome),
    revealOutcome,
  };
}
