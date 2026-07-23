import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const bundle = JSON.parse(
  await readFile(
    new URL(
      "../public/data/replays/v8-active-repair-direct.json",
      import.meta.url,
    ),
    "utf8",
  ),
);
const consoleSource = await readFile(
  new URL("../app/components/EvidenceConsole.tsx", import.meta.url),
  "utf8",
);
const consoleCss = await readFile(
  new URL("../app/components/industrial-console.css", import.meta.url),
  "utf8",
);
const directorSource = await readFile(
  new URL("../app/lib/replayDirector.ts", import.meta.url),
  "utf8",
);

test("selected-corridor snapshots preserve recorded actor, step and viewpoint", () => {
  const frames = bundle.sensor_frames
    .filter(
      (frame) => frame.corridor_id === bundle.outcome.selected_corridor,
    )
    .sort((a, b) => a.step - b.step);
  assert.deepEqual(
    frames.map(({ step, observer_agent_id, viewpoint }) => ({
      step,
      observer_agent_id,
      viewpoint,
    })),
    [
      {
        step: 167,
        observer_agent_id: "carrier",
        viewpoint: "carrier_initial_front",
      },
      {
        step: 1011,
        observer_agent_id: "scout",
        viewpoint: "corridor_a/left_near",
      },
    ],
  );
});

test("snapshot presentation explicitly says static and keeps MOVE on ROOT 01", () => {
  assert.match(consoleSource, /ROBOT-CAPTURED EVIDENCE SNAPSHOT/);
  assert.match(consoleSource, /静态快照 · 非连续视频/);
  assert.match(consoleSource, /侦察车移动中 · 当前仍显示 ROOT 01/);
  assert.match(consoleSource, /rootOrdinal/);
  assert.doesNotMatch(consoleSource, /CAMERA MOVES WITH SCOUT/);
});

test("snapshot media is 4:3 contained and never vertically cropped", () => {
  assert.match(consoleCss, /\.snapshot-media\s*\{[^}]*aspect-ratio:\s*4\s*\/\s*3/s);
  assert.match(consoleCss, /\.recorded-frame\s*\{[^}]*object-fit:\s*contain/s);
});

test("compact layout removes the duplicate timeline and stacks only below 900px", () => {
  assert.doesNotMatch(consoleSource, /<section className="timeline-panel">/);
  assert.match(
    consoleCss,
    /@media \(max-width: 1499px\) and \(min-width: 901px\)[\s\S]*?\.decision-summary\s*\{[\s\S]*?order:\s*-1/s,
  );
  assert.match(
    consoleCss,
    /@media \(max-width: 900px\)[\s\S]*?\.world-evidence-layout\s*\{[^}]*grid-template-columns:\s*1fr/s,
  );
  assert.match(consoleCss, /\.console-toolbar\s*\{[^}]*min-height:\s*52px/s);
  assert.match(consoleCss, /\.judge-stage\s*\{[^}]*min-height:\s*156px/s);
});

test("judge copy does not imply occlusion and names independent verification", () => {
  assert.match(directorSource, /This is not an occlusion finding/);
  assert.match(directorSource, /independent verification viewpoint/);
  assert.doesNotMatch(directorSource, /occlusion recovery/i);
});
