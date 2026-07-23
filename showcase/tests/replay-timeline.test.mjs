import assert from "node:assert/strict";
import test from "node:test";

import {
  ACTIVE_DURATIONS_MS,
  PASSIVE_DURATIONS_MS,
  advanceTimeline,
  chapterProgress,
  createPlaybackState,
  routeBeforeAction,
  seekPlayback,
  tickPlayback,
  timelineDurations,
  togglePlayback,
} from "../app/lib/replayTimeline.ts";

test("active and passive timelines are exactly 30 seconds", () => {
  assert.equal(ACTIVE_DURATIONS_MS.reduce((a, b) => a + b, 0), 30_000);
  assert.equal(PASSIVE_DURATIONS_MS.reduce((a, b) => a + b, 0), 30_000);
  assert.deepEqual(timelineDurations(true), ACTIVE_DURATIONS_MS);
  assert.deepEqual(timelineDurations(false), PASSIVE_DURATIONS_MS);
});

test("timeline advances once and stops on the final chapter", () => {
  assert.deepEqual(advanceTimeline(0, 6), {
    chapterIndex: 1,
    playing: true,
    completed: false,
  });
  assert.deepEqual(advanceTimeline(5, 6), {
    chapterIndex: 5,
    playing: false,
    completed: true,
  });
});

test("route is hidden until the action chapter", () => {
  assert.equal(routeBeforeAction("direct", false), "pending");
  assert.equal(routeBeforeAction("detour", false), "pending");
  assert.equal(routeBeforeAction("direct", true), "direct");
});

test("single replay clock pauses and resumes without jumping", () => {
  let state = createPlaybackState(true);
  state = tickPlayback(state, 12_000, ACTIVE_DURATIONS_MS);
  assert.equal(state.chapterIndex, 3);
  assert.equal(state.chapterElapsedMs, 1_000);
  assert.equal(chapterProgress(state, ACTIVE_DURATIONS_MS), 1 / 6);

  state = togglePlayback(state);
  const paused = tickPlayback(state, 4_000, ACTIVE_DURATIONS_MS);
  assert.deepEqual(paused, state);

  state = togglePlayback(paused);
  state = tickPlayback(state, 2_000, ACTIVE_DURATIONS_MS);
  assert.equal(state.chapterIndex, 3);
  assert.equal(state.chapterElapsedMs, 3_000);
});

test("seeking resets chapter time and completion is exact", () => {
  const sought = seekPlayback(4, ACTIVE_DURATIONS_MS);
  assert.equal(sought.chapterIndex, 4);
  assert.equal(sought.chapterElapsedMs, 0);
  assert.equal(sought.globalElapsedMs, 17_000);

  const complete = tickPlayback(
    createPlaybackState(true),
    30_000,
    ACTIVE_DURATIONS_MS,
  );
  assert.equal(complete.completed, true);
  assert.equal(complete.playing, false);
  assert.equal(complete.globalElapsedMs, 30_000);
  assert.equal(complete.chapterIndex, 5);
  assert.equal(chapterProgress(complete, ACTIVE_DURATIONS_MS), 1);
});
