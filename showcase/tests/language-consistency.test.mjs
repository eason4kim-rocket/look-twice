import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const root = new URL("../app/", import.meta.url);
const source = async (path) => readFile(new URL(path, root), "utf8");

test("uses one persistent language provider for every route", async () => {
  const [layout, shell, consoleSource] = await Promise.all([
    source("layout.tsx"),
    source("components/SiteShell.tsx"),
    source("components/EvidenceConsole.tsx"),
  ]);
  assert.match(layout, /<LanguageProvider>\{children\}<\/LanguageProvider>/);
  assert.match(shell, /look-twice\.locale/);
  assert.match(shell, /document\.documentElement\.lang/);
  assert.match(shell, /searchParams\.set\("locale", language\)/);
  assert.match(shell, /href=\{localizedHref\("\/console"\)\}/);
  assert.doesNotMatch(consoleSource, /query\.get\("locale"\)/);
  assert.doesNotMatch(consoleSource, /\{\s*language,\s*setLanguage\s*\}/);
});

test("localizes all judge-facing route headings and controls", async () => {
  const [home, results, reproduce, consoleSource, world] = await Promise.all([
    source("page.tsx"),
    source("results/page.tsx"),
    source("reproduce/page.tsx"),
    source("components/EvidenceConsole.tsx"),
    source("components/WorldReplay3D.tsx"),
  ]);
  for (const expected of [
    "AMD GPU · 物理 AI · 证据保障",
    "录制的 AMD GPU 证据",
    "证据保障在线",
    "获取新证据根",
  ]) {
    assert.match(home, new RegExp(expected));
  }
  for (const expected of [
    "锁定输入证据包",
    "它不能建立什么",
    "公开预注册挑战",
    "AMD 全流程墙钟遥测",
    "旧版独立补充",
    "能力边界",
    "冻结身份",
    "诚实边界",
    "已验证",
  ]) {
    assert.match(results, new RegExp(expected));
  }
  for (const expected of ["挑战优先的复现方式", "预注册挑战", "冻结 SHA 守卫", "原始证据"]) {
    assert.match(reproduce, new RegExp(expected));
  }
  for (const expected of [
    "公开预注册挑战结果",
    "预注册聚合结果",
    "动作授权",
    "最终路线",
    "PYTHON 门控",
    "不安全穿越",
    "原始回合 JSON",
  ]) {
    assert.match(consoleSource, new RegExp(expected));
  }
  for (const expected of ["录制轨迹回放", "机器人保持停止", "示意车体"]) {
    assert.match(world, new RegExp(expected));
  }
});

test("keeps technical values readable while translating their UI labels", async () => {
  const [consoleSource, shell] = await Promise.all([
    source("components/EvidenceConsole.tsx"),
    source("components/SiteShell.tsx"),
  ]);
  assert.match(consoleSource, /P（受阻）/);
  assert.match(consoleSource, /走廊掩码/);
  assert.match(consoleSource, /if \(value === "clear"\) return "畅通"/);
  assert.match(consoleSource, /if \(value === "blocked"\) return "受阻"/);
  assert.match(consoleSource, /predictionSetValue/);
  assert.match(shell, /lang=\{zh \? "en" : "zh-CN"\}/);
});
