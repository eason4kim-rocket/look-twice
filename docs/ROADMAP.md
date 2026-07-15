# Look Twice 参赛路线图

## V3 实施状态 — 2026-07-15

- [x] 连续场景随机化与 clear/blocked 分层 seed
- [x] ROCm Tensor 上的视角相关 RGB-D/segmentation 退化
- [x] 概率 belief、entropy、TTL 与 Action Gate
- [x] Fixed、Random、Information-Gain NBV
- [x] Learned NBV 数据、训练、测试与自动晋级门槛
- [x] CPU/ROCm 预热吞吐基准
- [x] 50 回合 GPU 冒烟矩阵
- [ ] 500 回合正式配对实验
- [ ] 200/50/100 场景 Learned NBV 正式训练
- [ ] v3 组合演示视频与最终参赛材料

V3 在独立 `v3-noisy-active-perception` 分支开发，v2 标签与正式结果保持不变。

## V2 完成状态 — 2026-07-15

- [x] Genesis RGB-D 与 entity segmentation
- [x] AMD ROCm PyTorch `cuda:0` 证据计算
- [x] 四候选点 Next-Best-View 规划器
- [x] `stale` belief 与全新证据 epoch
- [x] 动态障碍出现、消失和偏移遮挡
- [x] 20 回合冒烟矩阵
- [x] 120 回合正式对照实验
- [x] 动态主动感知演示视频

V2 正式实验源码提交为
`f7a4e32467b984ef236eadbd767a99001c64113e`。

## 1. 项目定位

**Look Twice: Evidence-gated active perception for safe navigation.**

中文定位：

> 一个通过证据结算与行动准入，实现安全导航的主动感知系统。

机器人面对无法确认的区域时，不盲目前进，也不永久停止。它会主动移动到更好的观察位置，累积证据，在证据足够可靠时才允许执行高风险动作。

## 2. 核心问题

普通单次观察系统可能会执行：

```text
一次观察为 clear
→ 立即通过
```

Look Twice + Purify 的目标是：

```text
观察证据
→ 证据累积与冲突检查
→ 状态结算
→ 行动准入
→ 直行、绕行或主动再观察
```

## 3. 系统边界

参赛版本优先完成小而完整的闭环，暂不引入：

- 强化学习；
- VLA 或大模型控制；
- ROS；
- 真实轮式动力学；
- 数据库和完整证据平台；
- 复杂视觉模型。

参赛版本应该优先保证：

- 逻辑可解释；
- 实验可复现；
- 两条路线稳定演示；
- 证据真实改变机器人行为；
- AMD GPU 使用有明确证据。

## 4. 系统数据链

```text
场景真值
→ 观察模型
→ Observation 证据
→ RegionBelief 结算
→ Action Gate 行动准入
→ 机器人运动
→ 运行指标
```

三个概念必须分开：

- `scenario`：世界实际上是什么；
- `observation`：机器人某次观察看到了什么；
- `belief`：Purify 根据多条证据最终相信什么。

## 5. 开发原则

本文档提供完整路线，但实际开发必须小步执行：

1. 每次只实现一个可观察行为；
2. 改动前明确目的、输入、输出和验收标准；
3. 只运行相关脚本；
4. 验收通过后再提交 Git；
5. 每个实验使用固定参数和随机种子；
6. 不在一次改动中同时开发感知、决策和可视化。

## 6. 里程碑

### M0：双路线状态机（已完成）

输入：

```text
--observation clear
--observation blocked
```

输出：

```text
clear   → inspection → goal
blocked → inspection → detour → goal
```

已完成：

- `GO_TO_DETOUR` 状态；
- clear/blocked 分支；
- 绕行点；
- 路线摘要；
- 最终实体位置一致性修复。

### M1：场景驱动的观察（已完成）

目的：

> 不再直接告诉机器人观察结论。

输入：

```text
--scenario clear
--scenario blocked
```

行为：

- clear 场景不在受检区域放置障碍；
- blocked 场景在受检区域放置障碍；
- 机器人只在到达观察点后读取场景证据；
- 观察函数输出 `clear` 或 `blocked`。

验收：

- 命令行不再接受最终观察结论；
- 场景配置与观察结果一致；
- 两条路线都到达目标；
- 相同命令重复运行结果一致。

### M2：最小证据记录（已完成）

新增最小数据结构：

```python
Observation(
    viewpoint: str,
    result: str,
    confidence: float,
    step: int,
)
```

要求：

- 每次观察产生一条证据；
- 日志能回答“机器人为什么做出这个决定”；
- 本阶段只保存内存列表，不引入数据库。

验收：

- 运行结束后打印完整证据摘要；
- 每条证据包含观察点、结果、置信度和步数。

### M3：Purify 状态结算和行动准入（已完成）

最小状态集：

```text
unknown
provisional_clear
provisional_blocked
uncertain
confirmed_clear
confirmed_blocked
```

最小规则：

```text
第一次观察
→ provisional

两次同向观察
→ confirmed

两次观察冲突
→ uncertain

confirmed_clear
→ 允许直行

confirmed_blocked
→ 必须绕行
```

最小接口：

```python
add_observation()
resolve_state()
is_action_allowed()
```

验收：

- 单次 clear 不能直接获得高风险通行权；
- 证据不足时机器人不进入目标区域；
- 决策日志显示当前 belief 和准入结果。

### M4：冲突触发第二观察点（已完成）

新增：

- `inspection_left_xy`；
- `inspection_right_xy`；
- `GO_TO_SECOND_INSPECTION`。

行为：

```text
证据一致
→ 允许决策

证据不足或冲突
→ 前往另一观察点
→ 获取新证据
→ 重新结算
```

验收：

- 无冲突时不增加额外路程；
- 冲突时实际移动到第二观察点；
- 第二次观察真实改变后续行动。

### M5：噪声模型与对照实验（已完成）

观察模型加入可控噪声：

- 误检；
- 漏检；
- 遮挡；
- 置信度波动。

对照系统：

| 系统 | 决策方式 |
| --- | --- |
| Single Shot | 相信一次观察 |
| Majority Vote | 固定观察三次后多数投票 |
| Look Twice + Purify | 根据证据质量和冲突决定是否继续观察 |

指标：

- 不安全穿越率；
- 成功到达率；
- 错误绕行率；
- 平均观察次数；
- 平均路径长度；
- 任务完成时间。

所有实验必须记录：

- 随机种子；
- 场景参数；
- 噪声参数；
- 硬件与软件版本；
- 原始结果和汇总结果。

### M6：可视化与演示（已完成）

演示必须直接显示：

- 机器人位置和历史轨迹；
- 当前任务状态；
- 当前 region belief；
- 观察证据和置信度；
- Action Gate 允许或拒绝的动作；
- clear 与 blocked 的不同路线。

主演示视频目标时长：60–90 秒。

### M7：提交和冻结

最终产物：

- 中英文 README；
- 系统架构图；
- 主演示视频；
- 对照实验表格和图表；
- AMD GPU 环境和性能数据；
- 可复现命令；
- 已知局限；
- GitHub 开源仓库；
- `v1.0-hackathon` Git tag。

## 7. 时间表

最终提交截止：**2026-08-06 23:59**。

| 日期 | 目标 |
| --- | --- |
| 7 月 15–18 日 | 稳定双路线基线（已完成） |
| 7 月 19–21 日 | M1 场景驱动观察 |
| 7 月 22–24 日 | M2 证据记录 |
| 7 月 25–27 日 | M3 状态结算与行动准入 |
| 7 月 28–30 日 | M4 冲突驱动的主动再观察 |
| 7 月 31 日–8 月 2 日 | M5 对照实验 |
| 8 月 3–4 日 | M6 可视化和视频 |
| 8 月 5 日 | 文档、复现检查、提交和冻结 |
| 8 月 6 日 | 缓冲，不安排主要开发 |

## 8. 获奖判断标准

项目是否具有竞争力，不由代码量决定，而由以下问题决定：

1. 证据是否真实改变了机器人行为？
2. 证据不足时，系统是否真的拒绝高风险动作？
3. 证据冲突时，机器人是否会主动换位置获取新证据？
4. 是否用对照实验证明安全性改善？
5. 是否能在 60 秒内让评委看懂问题、方法和结果？
6. AMD GPU 是否承担了可验证的仿真或批量评估工作？

## 9. 当前下一步

核对官方提交页字段和视频要求，完成最终剪辑后创建 `v1.0-hackathon` 标签。
