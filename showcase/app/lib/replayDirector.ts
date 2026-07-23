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
      title: zh ? "走廊看起来可以通行" : "The corridor looks clear",
      body: zh
        ? "但它只来自一个正面采集根，仍不足以授权真实物理动作。"
        : "But the claim comes from one front capture root—insufficient to authorize physical action.",
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
        ? "动作合同缺少独立侧视证据。更多同源 Claim 不会增加保障。"
        : "The action contract lacks independent side-view evidence. More correlated claims would not add assurance.",
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
          ? "NBV 选择能修复合同缺口的诊断视角，而不是盲目重拍。"
          : "NBV selects a diagnostic viewpoint that can repair the contract—not a blind retry.",
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
          ? "机器人协同移动到独立侧视位置"
          : "The robots reposition for an independent side view",
        body: zh
          ? "Scout 获取新物理采集根；Carrier 同时沿记录的接近轨迹连续移动。"
          : "The scout acquires a new physical capture root while the carrier follows its recorded approach trajectory.",
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
          ? "新的 RGB-D Claim 被校准、纳入谱系；Python 与 Purify Go 同时准入。"
          : "The new RGB-D claim is calibrated and lineage-aware; Python and Purify Go both admit.",
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
          ? "最终路线 DIRECT，unsafe=0。证据改变了动作资格。"
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
