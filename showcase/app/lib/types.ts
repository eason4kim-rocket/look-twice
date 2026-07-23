export type Localized = { en: string; zh: string };
export type ReleaseProfile = {
  schema_version: string; candidate_id: string; display_name: string; tagline: Localized;
  capabilities: string[]; headline_metrics: Array<{metric_id:string; value:number; denominator:number; label:Localized; source:string}>;
  artifact_identities: Array<{artifact:string; sha256:string}>; limitations: Localized[];
  experiment_links: Array<{label:string;href:string}>; default_replays: string[]; profile_sha256:string;
};
export type GateReceipt = { receipt_sha256?:string; corridor_id?:string; evaluated_step:number; decision?:string; admitted:boolean; python_admitted:boolean; purify_go_admitted:boolean; effective_admit:boolean; p_blocked?:number; reasons:string[]; belief_gaps:string[]; measurement_root_ids:string[]; claim_count:number };
export type GateReceiptV11 = {
  gate_id:string; source_receipt_sha256?:string; corridor_id?:string;
  evaluated_step:number; decision?:string; admitted:boolean;
  python_admitted:boolean; purify_go_admitted:boolean; effective_admit:boolean;
  p_blocked?:number; reasons:string[]; belief_gaps:Array<string|Record<string,unknown>>;
  measurement_root_ids:string[]; claim_count:number;
};
export type MotionPoint = {step:number;x:number;y:number;yaw:number};
export type MotionSegment = {
  motion_id:string; agent_id:string;
  purpose:"approach"|"scout_repair"|"direct_cross"|"safe_detour"|string;
  start_step:number; end_step:number; reached:boolean; collision_count:number;
  path_length:number; target_xy:number[]; final_pose:Record<string,number>;
  trajectory_sample:MotionPoint[];
};
export type ReplayEvent = {
  event_id:string;step:number;type:string;status:string;title_key:string;
  ref_kind:"sensor_frame"|"gate_receipt"|"repair_request"|"motion_segment"|"outcome";
  ref_id:string;
};
export type EpisodeBundle = {
  schema_version:string; candidate_id:string;
  episode_meta:{replay_id:string;profile:string;seed:number;policy:string;runtime:string;device:string;gpu:string;corridors:Array<{id:string;region:number[];width:number}>;recorded_gpu_evidence:boolean;simulation_only:boolean;frozen_candidate_artifact:boolean;live_gpu_dependency:boolean};
  sensor_frames:Array<{frame_id:string;step:number;corridor_id:string;viewpoint:string;value:string;p_blocked:number;prediction_set:string[];tensor_device:string;input_sha256:string;media:{rgb:string;depth:string;corridor_mask:string;available:boolean;sha256:Record<string,string>}}>;
  claims:Array<Record<string,unknown>>; measurement_roots:Array<{measurement_root_id:string;source_capture_root_ids:string[];device_root_ids:string[];observer_agent_id?:string;observed_step:number;claim_ids:string[]}>;
  gate_receipts:GateReceiptV11[]; repair_requests:Array<Record<string,unknown>>; nbv_candidates:Array<Record<string,unknown>>; motion_segments:MotionSegment[];
  events:ReplayEvent[];
  outcome:{mission_success:boolean;unsafe_crossing:boolean;route_mode:string;repair_attempted:boolean;repair_success:boolean;initial_gate_denied:boolean;new_capture_root_added:boolean;selected_corridor:string;observation_count:number;replan_count:number};
  integrity:{builder_version:string;source_episode_sha256:string;frozen_identity:Record<string,string>;recorded_media_manifest_sha256?:string;bundle_sha256:string};
};
