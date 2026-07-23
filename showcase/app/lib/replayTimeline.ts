export const ACTIVE_DURATIONS_MS = [3000, 4000, 4000, 6000, 5000, 8000];
export const PASSIVE_DURATIONS_MS = [6000, 8000, 16000];

export type ReplayPlaybackState = {
  chapterIndex: number;
  chapterElapsedMs: number;
  globalElapsedMs: number;
  playing: boolean;
  completed: boolean;
};

export type TimelineStep = {
  chapterIndex: number;
  playing: boolean;
  completed: boolean;
};

export function timelineDurations(active: boolean) {
  return active ? ACTIVE_DURATIONS_MS : PASSIVE_DURATIONS_MS;
}

export function advanceTimeline(
  chapterIndex: number,
  chapterCount: number,
): TimelineStep {
  if (chapterIndex >= chapterCount - 1) {
    return {
      chapterIndex: Math.max(0, chapterCount - 1),
      playing: false,
      completed: true,
    };
  }
  return {
    chapterIndex: chapterIndex + 1,
    playing: true,
    completed: false,
  };
}

export function routeBeforeAction(routeMode: string, isActionChapter: boolean) {
  return isActionChapter ? routeMode : "pending";
}

export function createPlaybackState(
  playing = false,
): ReplayPlaybackState {
  return {
    chapterIndex: 0,
    chapterElapsedMs: 0,
    globalElapsedMs: 0,
    playing,
    completed: false,
  };
}

export function chapterProgress(
  state: ReplayPlaybackState,
  durations: number[],
) {
  const duration = durations[state.chapterIndex] || 1;
  return Math.max(0, Math.min(1, state.chapterElapsedMs / duration));
}

export function seekPlayback(
  chapterIndex: number,
  durations: number[],
): ReplayPlaybackState {
  const safeIndex = Math.max(0, Math.min(durations.length - 1, chapterIndex));
  return {
    chapterIndex: safeIndex,
    chapterElapsedMs: 0,
    globalElapsedMs: durations
      .slice(0, safeIndex)
      .reduce((sum, duration) => sum + duration, 0),
    playing: false,
    completed: false,
  };
}

export function togglePlayback(
  state: ReplayPlaybackState,
): ReplayPlaybackState {
  if (state.completed) return createPlaybackState(true);
  return { ...state, playing: !state.playing };
}

export function tickPlayback(
  state: ReplayPlaybackState,
  deltaMs: number,
  durations: number[],
): ReplayPlaybackState {
  if (!state.playing || state.completed || deltaMs <= 0 || !durations.length) {
    return state;
  }
  let chapterIndex = state.chapterIndex;
  let chapterElapsedMs = state.chapterElapsedMs;
  let remaining = deltaMs;
  while (remaining > 0) {
    const duration = durations[chapterIndex] || 1;
    const available = Math.max(0, duration - chapterElapsedMs);
    if (remaining < available) {
      chapterElapsedMs += remaining;
      remaining = 0;
      break;
    }
    remaining -= available;
    if (chapterIndex >= durations.length - 1) {
      chapterElapsedMs = duration;
      return {
        chapterIndex,
        chapterElapsedMs,
        globalElapsedMs: durations.reduce((sum, item) => sum + item, 0),
        playing: false,
        completed: true,
      };
    }
    chapterIndex += 1;
    chapterElapsedMs = 0;
  }
  return {
    chapterIndex,
    chapterElapsedMs,
    globalElapsedMs: Math.min(
      durations.reduce((sum, item) => sum + item, 0),
      state.globalElapsedMs + deltaMs,
    ),
    playing: true,
    completed: false,
  };
}
