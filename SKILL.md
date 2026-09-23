---
name: fragile-question-map
description: 设计讨论同时牵涉多个待决问题、需要先看全局再逐个深挖时使用：把 Seed、材料或对话整理成问题地图，只选一个区域交给 grilling 一次一问，并记录纠正、验证与原型迭代。也用于继续已有地图、处理对已确认决定的明确纠正，或判断原型结果能否写回与关闭。不用于清晰的单点实现，不替代 grilling、prototype、research 或 to-spec。
---

# Fragile Question Map

建立当前 destination 内的问题地图，保存设计与验证关系，并把深度工作交给已有 skills。

核心原则：**批量看全局，一次做一个决定。**

## Core rules

- 能从代码、文档、Seed 或现状查到的事实先查，不问用户。
- 先做 provenance、scope、批量提取、Intent 聚类、去重和依赖识别；进入 `grilling` 后才一次只问一个主问题。
- 默认向用户展示人话：候选区域、影响、推荐选择和下一步；只有用户要求地图结构时才展示 `status`、`resolution`、`verification`、`closure` 等内部字段。
- `possible_gaps` 只保存模型推测的潜在缺口，不自动变成 Question、候选区域或 blocker。
- 不把所有关系都标成 blocker；当前切片能继续时保留为 `informs`、`depends_on` 或 Park。
- 不在共享理解形成前执行方案；不把 Question Map 变成 backlog、路线图或完整跨 Seed 编排系统。
- 不得自动启动 `$fragile-skill-prototype`；只在用户确认运行模式与 A/B/C 交接后提供显式调用入口。

## Workflow

### 1. 找到或新建地图

地图存放在项目根目录（当前工作区）的 `.question-map/<question_map_id>/` 下：

```text
.question-map/<question_map_id>/
├── question-map.json
├── briefs/        # Prototype Run Brief
└── seeds/         # 返回的 Seed
```

开始前先运行只读的 `python3 scripts/list-question-maps.py <project-root>`：

- 已有与当前 destination 对应、`closure` 不是 `superseded` 的地图：继续它，先用 `report-question-map.py` 向用户复述当前区域与下一步；
- 有多张候选：列出并让用户选，不要自己合并；
- 没有：从 [references/examples/fragile-learn/](references/examples/fragile-learn/) 复制结构新建，先读 [references/question-map-schema.md](references/question-map-schema.md)。

新地图必须声明 `schema_version`；Seed、Brief 引用写相对于地图文件的路径。用户指定了其他位置时照用户的。是否提交 `.question-map/` 由用户决定。

### 2. 划定范围并导入

先写清 `destination`、当前 `scope`、`out_of_scope` 和来源。输入是 `Skill Interaction Seed` 时，只有在需要时读取 [references/skill-interaction-seed-adapter.md](references/skill-interaction-seed-adapter.md)；核心流程只消费 adapter 产生的通用批次，不依赖某个学习 skill 的私有字段。

批量提取并保留 provenance：

- `chosen`、`rejected`、`sibling`、`open`、`corrections`、`insights`；
- Seed lineage、`full` / `changed_slice`、tested slice 和重跑建议；
- 用户纠正前后的原文、来源回合和受影响 Intent；
- `possible_gaps` 单独保留，不自动导入 Grill。

### 3. 生成候选区域

按 Intent 聚类、去重并识别依赖，向用户展示 2–3 个候选区域。每个区域只说明：要决定什么、已有证据、会影响哪一条范围或验收。把未选区域标为 sibling/later/deferred，保留理由；不要逐条请求确认。

用户选择一个区域后，只有该区域进入当前 `grilling`；其他区域继续留在地图中。

### 4. 分类并一次一问

为每个问题记录稳定 ID、Intent、具体问题、证据要求、类型化关系、`confidence` 和生命周期字段：

| Mode | Route | 默认状态 |
|---|---|---|
| `discuss` | 使用 `grilling`，一次一问 | `open` → `resolved` |
| `verify` | 使用 `prototype` 或有边界 R&D，先写 `evidence_needed` 和 verification plan | `open` / `deferred` |
| `fact` | 查代码、材料、运行状态或高可信资料 | `resolved` |
| `park` | 保存 Intent、来源和暂缓理由，不打断当前 Grill | `deferred` |

`confidence` 表示证据把握，不承担决策完成状态。`resolution` 保存结论、证据、确认时间和 supersession；`verification` 分开保存计划与执行结果。

### 5. 处理明确纠正

如果用户明确纠正已经确认的决定：

1. 保留原 Question、原 Intent 和原证据；
2. 将旧 Question 设为 `status=superseded`，在 `resolution.superseded_by` 指向替代 Question；
3. 为前后变化写一条 `delta`（通常为 `invalidated` 或 `scope_change`），目标可以是旧 Question 或 baseline Node；
4. 只追问纠正后仍有歧义的一个问题，不重新打开已被纠正的整段 Grill。

未明确纠正时，不替用户把新想法解释成 supersession。

### 6. 路由灵感与选择学习切片

单条突发灵感先原样保存 `raw` 和 `origin`，再只问一次：

> 如果完全不处理这个灵感，当前切片能否在不改变目标、验收标准和关键范围的前提下继续？

根据回答路由到 `current`、`bubble_up`、`informs`、`park` 或 `build_dependency`；若形成新设计意图，设置有效 `intent_id`，不要静默压进当前问题。

只有未解决的 Verify 同时直接阻塞决定/构建、且讨论和事实查找不足以回答时，才触发 Learning Prototype。每个 MVP slice 必须引用 baseline parent；MVP 是投影，不覆盖 baseline。

### 7. 原型迭代交接

当前区域同时具备明确 delta 和 evidence goal 时，进入 `ready_for_rerun`，并**先读** [references/prototype-iteration-handoff.md](references/prototype-iteration-handoff.md)：它规定 full / changed_slice 推荐、Brief、A/B/C 交接、返回 Seed 写回、第 3 次重跑 WARNING，以及接受与整合验证的区分。未到这一步时不需要读。

### 8. 回写与关闭

每次 Discuss、Verify、Fact、prototype 或实现结束后更新问题状态、resolution、verification、关系、baseline rationale 和 delta。当前 blocker 只表示现在仍阻塞；历史通过 supersession 和 delta 保留。

`closure` 只描述当前阶段：

- `active`：仍在收敛；
- `design_closed`：当前设计切片可以交给下游，但 remaining verifications 尚未全部通过；
- `fully_verified`：当前范围内的 Verify 已有通过证据；
- `superseded`：当前地图被更高层方向替代。

关闭地图不等于所有 Verify 已通过；`possible_gaps` 也不自动阻止 `design_closed`。

### 9. 委托下游

- 深度对齐：`grilling`
- 高保真未知：`prototype`
- 事实或外部证据：代码检查或 `research`
- 巨大 fog：`wayfinder`
- 对齐后的规格：`to-spec`
- 实现任务：`to-tickets`
- 实施：`implement`
- 跨 session：`handoff`

Question Map 保存设计、验证、来源和回写关系。执行依赖以 tracker 或下游 skill 的真实产物为真源，不用本地 JSON 声称 native edge 或真实副作用已经存在。

## Scripts

在本 Skill 目录运行（Python 3.8+，只用标准库）；除 validator 的退出码外都只读：

```bash
python3 scripts/list-question-maps.py <project-root>
python3 scripts/validate-question-map.py <question-map.json>
python3 scripts/validate-prototype-run-brief.py <prototype-run-brief.md>
python3 scripts/report-question-map.py <question-map.json>
```

每次写入地图后运行 validator。硬错误必须修正；WARNING 提示生命周期、closure、候选依赖或扩展字段风险，由你判断并告诉用户。validator 只证明结构与引用，不证明策略正确。

## Final response

交付时用人话说明：

- 地图位置、destination、选中的一个切片和候选区域概览；
- 主要问题及其 mode/status，直接 blocker 与当前 closure；
- 被 Park、sibling、rejected 或保留在 MVP 外的 Intent；
- 进入原型迭代时：运行模式（推荐与选择）、Brief、A/B/C 交接、rerun count、acceptance 与 integration；
- 下一步调用哪个 skill；
- 是否运行了 validator/report，以及它们实际证明的边界。
