# 适配记录：DSH 0.2.1-rc.2

本分支在 `lib/core.js` 的 `PATCHES` 表上做了最小改动，让 v1.1.71 在 DSH **0.2.1-rc.2** 上重新对齐。
未改动任何补丁的语义逻辑，只更新锚点与目标文件路由。

## 基线

| 阶段 | applied | na | pending | skipped | missing_file |
|---|---:|---:|---:|---:|---:|
| 适配前（0.2.1） | 62 | 14 | 0 | 5 | 1 |
| 适配后（0.2.1） | 62 | 14 | **3** | 2 | 1 |

`pending` 表示"锚点已命中、待执行 apply"，是适配成功的信号。实际 apply 后预期 `applied` 增至 65。

## 改动清单

### 1. 新增目标路由 `harness-dev-context`

0.2.1 把 web 面身份句从 `dsh-web-app/lib/index.js` 迁到了 `dsh-harness-dev-context/lib/index.js`。

```js
"harness-dev-context": firstExisting([
  path.join(aiBase, "dsh-harness-dev-context", "lib", "index.js"),
  ...(root ? [path.join(root, "packages", "context", "harness-dev-context", "lib", "index.js")] : []),
]),
```

### 2. `#32 WEB_SURFACE_IDENTITY_NEUTRAL`

- `file`: `["web-app-lib"]` → `["harness-dev-context", "web-app-lib"]`（保留旧路径以兼容旧版）
- 新增 3 条替换，覆盖 0.2.1 的三种新形态：
  - `WEB_SURFACE_PROMPT` 模板字面量（`whose URL the runtime context names`）
  - `LEGACY_WEB_SURFACE.prefix` 里残留的旧自称
  - 新增的 `Current DeepSeek Harness Web GUI URL: ...` 上下文行

### 3. `#53 WEB_SURFACE_PROHIBITION`

- `file`: `["web-app-lib"]` → `["harness-dev-context"]`
- 新增一条：把 0.2.1 新句式收成 `Local web GUI.`
- 原有 `Do not start a replacement server ...` 删除规则在 0.2.1 仍然命中，未改动

### 4. `#77 REWIND_DROP_SENT_ON_APPEND`

0.2.1 在 `append(record)` 里插入了一行守卫，锚点断裂：

```diff
  append(record) {
      const event = record.event;
      if (this.inputs.has(event.seq)) return "none";
+     if (this.revised.size > 0) this.revised.clear();
      this.inputs.set(event.seq, record);
```

`pattern` 与 `replace` 同步跟随该行，注入位置不变。

## 未处理项（非缺陷）

| # | 名称 | 说明 |
|---|---|---|
| 40 | `COMPLETE_PROMPT_KEEP_INJECT` | 目标文件已含 4 处 `dsh-purge` 标记，实际已生效；`skipped` 是状态计算误报（首个 replacement 的 `pattern` 为占位对象 `{}`） |
| 80 | `MINIMAL_OFFICIAL_TOOLSET` | minimal 预设已是官方态，无需改动 |
| 71 | `LIANGSHEN_IDENTITY_LINE` | 0.2.1 已移除梁神预设，目标文件不存在，属于上游删功能 |

## 校验方式（无需重启宿主）

```js
import * as core from 'dsh-purge/lib/core.js';
const aiBase = '/Applications/DeepSeek Harness.app/Contents/Resources/app/dsh/node_modules/@deepseek-ai';
const st = await core.patchStatus(aiBase);
// 期望：pending 3 / skipped 2 / missing_file 1 / applied 62 / na 14
```

上游每次升级后重跑一次即可判断锚点是否再次漂移。

## 署名

基于 [YuJunZhiXue/dsh-purge](https://github.com/YuJunZhiXue/dsh-purge) v1.1.71（MIT）。
原作者署名与 LICENSE 保留；本项目仅为版本适配分支，不改变原功能语义，不用于商业售卖。

---

## 第二轮：清零 3 项跳过

| # | 原状态 | 处理 | 结果 |
|---|---|---|---|
| 40 | skipped | 原 `pattern` 是 0.2.0 形态的正则，0.2.1 在 `system-prompt/assemble` 处新增 `requiredContexts` 行并改了 contexts 过滤 → 重写正则与替换产物，保留新语义 | pending → 应用后 applied |
| 71 | missing_file | 0.2.1 已移除梁神预设，目标不存在属预期 → 标记 `optional: true` | na |
| 80 | skipped | optional 补丁未命中却被计入跳过 → 状态规则改为 `optional && skipped → na` | na |

改后分布：`applied 65 / na 16 / pending 1`，**skipped 与 missing_file 均为 0**。
应用 #40 后为 `applied 66`。

### 关键代码位置

- `lib/core.js` `COMPLETE_PROMPT_WATERFALL_INJECT`：替换产物补 `const requiredContexts = ...`，contexts 改回 `transformed.contexts.filter((entry) => requiredContexts.has(entry.name))`
- `lib/core.js` `patchStatus()`：`else if (skipped > 0) status[p.id] = p.optional ? "na" : "skipped";`
