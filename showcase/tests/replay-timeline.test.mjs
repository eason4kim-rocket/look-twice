import assert from "node:assert/strict";
import test from "node:test";

import {
  ACTIVE_DURATIONS_MS,
  PASSIVE_DURATIONS_MS,
  advanceTimeline,
  routeBeforeAction,
  timelineDurations,
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
