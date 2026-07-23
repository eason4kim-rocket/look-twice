export const ACTIVE_DURATIONS_MS = [3000, 4000, 4000, 6000, 5000, 8000];
export const PASSIVE_DURATIONS_MS = [6000, 8000, 16000];

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
