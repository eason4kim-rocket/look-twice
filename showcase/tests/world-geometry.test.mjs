import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import {
  boxOverlapRatio,
  chapterStepAtProgress,
  createProjection,
  interpolatePose,
  projectedRobotBox,
  sceneBounds,
  trajectoryPoints,
} from "../app/lib/worldGeometry.ts";

const bundle = JSON.parse(
  await readFile(
    new URL(
      "../public/data/replays/v8-active-repair-direct.json",
      import.meta.url,
    ),
    "utf8",
  ),
);

test("recorded motion interpolation is deterministic", () => {
  const scout = trajectoryPoints(bundle, "scout");
  const first = interpolatePose(scout, scout[0].step);
  const middle = interpolatePose(
    scout,
    Math.round((scout[0].step + scout.at(-1).step) / 2),
  );
  const last = interpolatePose(scout, scout.at(-1).step);
  assert.deepEqual(first, scout[0]);
  assert.deepEqual(last, scout.at(-1));
  assert.notDeepEqual(middle, first);
  assert.notDeepEqual(middle, last);
});

test("MOVE and ACT map playback progress onto recorded world steps", () => {
  const moveStart = chapterStepAtProgress(bundle, "move", 164, 0);
  const moveEnd = chapterStepAtProgress(bundle, "move", 164, 1);
  const actStart = chapterStepAtProgress(bundle, "act", 1407, 0);
  const actEnd = chapterStepAtProgress(bundle, "act", 1407, 1);
  assert.equal(moveStart, 164);
  assert.equal(moveEnd, 662);
  assert.ok(actEnd > actStart);
});

test("step 662 keeps recorded separation and avoids projected body overlap", () => {
  const carrier = interpolatePose(trajectoryPoints(bundle, "carrier"), 662);
  const scout = interpolatePose(trajectoryPoints(bundle, "scout"), 662);
  const distance = Math.hypot(carrier.x - scout.x, carrier.y - scout.y);
  assert.ok(Math.abs(distance - 0.8459997491668393) < 1e-9);

  const projection = createProjection(1000, 500, sceneBounds(bundle));
  const carrierBox = projectedRobotBox(
    projection,
    carrier,
    bundle.episode_meta.agent_geometry.carrier.collision_width_m,
  );
  const scoutBox = projectedRobotBox(
    projection,
    scout,
    bundle.episode_meta.agent_geometry.scout.collision_width_m,
  );
  assert.ok(boxOverlapRatio(carrierBox, scoutBox) < 0.1);
});
