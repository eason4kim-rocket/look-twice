# Look Twice v3 design

## 定位

Look Twice v3 研究的是：在动态、遮挡和视角相关传感器退化同时存在时，
机器人应该相信当前证据、继续观察，还是安全绕行。

```text
randomized Genesis scene
→ raw RGB/depth/entity segmentation
→ view-dependent corruption on ROCm tensors
→ probabilistic belief and entropy
→ information-gain viewpoint utility
→ temporal Action Gate
→ proceed, reinspect, or detour
```

Genesis entity segmentation 是透明披露的模拟传感器代理，不是训练视觉模型。
v3 会保存 raw 与 corrupted 证据，使每次判断可以审计。

## 数据隔离

在线规划器只能读取：

- 当前 `p_blocked` 与 entropy；
- 已知静态遮挡物；
- 候选点距离和可达性；
- 历史观察质量；
- 预测传感器退化。

未知障碍物位置、干净 segmentation 和未来观察不能进入规划特征。它们只用于：

- Genesis 世界构建；
- 离线评价；
- `--collect-oracle-labels` 数据集生成。

## 可复现噪声

`ScenarioSample(profile, seed)` 决定场景几何、事件、可达性和噪声强度。
偶数 seed 初始 clear，奇数 seed 初始 blocked，保证配对实验分层平衡；
其余变量保持连续随机。

每条传感器证据使用：

```text
SHA256(global seed, observation index, viewpoint name)
```

派生独立随机种子。退化包括距离相关深度噪声、深度空洞、mask
腐蚀/膨胀、漏检、有限误检和 RGB 亮度/噪声变化。所有操作在传入的
PyTorch device 上执行。

## 概率 belief 与行动准入

`ProbabilisticRegionBelief` 使用带质量权重的 log-odds：

- blocked 增加 log-odds；
- clear 减少 log-odds；
- inconclusive 不提供方向，只使旧结论向未知衰减；
- belief 记录 `p_blocked`、二元熵、证据权重和校准轨迹；
- confirmed belief 超过 TTL 后变为 stale，并从 0.5 先验开始新 epoch。

只有 `confirmed_clear` 能通过风险区 Action Gate。uncertain、stale、
provisional 和 unresolved 都只能继续观察或安全绕行。

## Next-Best-View

```text
utility =
expected entropy reduction
- 0.25 × normalized travel cost
- 0.20 × revisit penalty
- 0.30 × predicted sensor degradation
```

重访是软惩罚而不是硬禁止：高质量原视角仍可能值得复看，系统性遮挡时则
应切换视角。Fixed、Random 和 Information-Gain 使用同一个首视角，只有
首证据不足后才产生策略差异。

## Learned NBV 晋级门槛

训练数据通过离线渲染全部候选点得到，标签是真实熵下降减移动成本。数据按
seed 隔离为 200 train、50 validation、100 test 场景。小型共享 MLP 只有在：

1. 独立 test split 的 oracle regret 低于 heuristic；
2. 正式策略回合不降低安全率；

两项同时满足时才进入演示。失败模型保留结果，但不能宣称优于启发式。

## 复现

```bash
/opt/venv/bin/python src/look_twice_v3.py \
  --profile dynamic-change \
  --policy purify-information-gain \
  --seed 20000 \
  --evidence-dir outputs/v3-evidence \
  --json-output outputs/v3-result.json

/opt/venv/bin/python scripts/run_v3_experiments.py \
  --output-dir outputs/v3-formal \
  --seed-count 20 \
  --seed-offset 20000 \
  --python /opt/venv/bin/python
```
