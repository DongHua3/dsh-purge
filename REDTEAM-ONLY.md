# redteam-only 分支说明

本分支由 `MyHead-Exploded/dsh-purge` 从上游 `6c1d638`（2026-10-12「暂停更新说明」）分出，
只做一件事：**把这个插件的破甲能力装进「红队模式」预设，并且不出现演练台悬浮坞。**

## 改了什么（相对上游，共 2 个文件 10 行）

### 1. `package.json` —— 删除 `dsh.client`

```diff
     "bundle": { "patch": "./cordis.patch.yml" },
-    "client": {
-      "platform": "web",
-      "inject": [
-        "@deepseek-ai/dsh-client-connection",
-        "@deepseek-ai/dsh-client-runtime",
-        "@deepseek-ai/dsh-client-locale",
-        "@deepseek-ai/dsh-client-ui-slots",
-        "@deepseek-ai/dsh-client-ui-settings"
-      ]
-    },
     "install": { ... }
```

**为什么这就够了**：客户端半边是宿主按「行的模块解析出的包 → 该包 `package.json` 的 `dsh.client`」
扫描加载的（`@deepseek-ai/dsh-client-modules` 的 `resolveMeta`/`parseDshClient`）。
字段不存在 → 不生成客户端模块行 → `client.js` 永不加载 → 那个注册在 `shell.overlay`
（id `dsh-purge-dock`）的悬浮坞和输入框右侧的回退按钮都不会出现。

顺带去掉了一条已经失效的声明：`@deepseek-ai/dsh-client-runtime` 在 DSH 0.2.x 里
已不存在（全树 0 命中）。

**要用回演练台**：把上面那段 `client` 块恢复即可（`git revert` 本分支的 package.json 改动）。

### 2. `lib/index.js` —— 新增 `redteamOnly` 配置项与两道门禁

```diff
 const DEFAULTS = {
   ...
   hooksDenyBypass: true,
+  redteamOnly: false,
 };
```
```diff
     text: (context) => {
       if (!injectAllowedNow(config)) return "";
+      if (config.redteamOnly === true && !isRedteamSession(context)) return "";
       return escapeDshInterpolation(peelChatmlEnvelope(adaptInjectForMinimalPreset(readInjectFallback(context), context)));
     },
```
`dshpg-capabilities` 段同样加了一道。

默认 `false` = 与上游行为完全一致；只有预设行里显式写 `redteamOnly: true` 才生效。

**为什么这一层是「二道保险」而不是主机制**：作用域主要由**行挂在哪里**决定——
把插件行挂在「红队模式」预设内部，`addPromptSection` 的注册就落进预设的 scope，
普通会话天然看不到（实测：standard 预设 24 段里没有破甲段，redteam 28 段里有）。
但 `addPromptSection` 会先试着往 `ctx.systemPrompt.ctx` 推一次、目标是全局层
（源码注释：「提示词服务自己的 ctx 多半没有 scope，段会进全局层」），
万一那条路径生效，非红队会话就会被注入。这道 gate 兜住那种情况。

返回空串是安全的：宿主 `renderPrompt` 的文档与实现都是 "drop empty sections"
（`filter(text => typeof text === 'string' && text.length > 0)`），
不会留下空标题。

## 怎么用

预设里挂**一行**（顶层，不要放进 `purge-plane` 那个 isolate 组——本插件不 `provide` 任何服务，
按上游模板自己的规则，不需要 realm）：

```yaml
- id: purge-core
  name: /Users/cyberpsychosis/Dsh/dsh-purge-fork/lib/index.js
  inject: [systemPrompt, tools]
  config:
    enabled: true
    autoApplyOnStart: false      # 关键：boot 绝不写宿主包
    autoUpdateOnStart: false
    autoRevertOnMissing: false
    redteamOnly: true            # 关键：只投给红队模式
    ...其余照上游 cordis.patch.yml 的默认值
```

用**绝对路径**挂载的好处：不需要 `pnpm install`、不动 profile 的 `package.json` /
`pnpm-lock.yaml` / 市场状态，改这个 worktree 里的代码即刻生效。
（先例：`~/.dsh/purge-standalone/prompt-section.mjs` 就是这么挂的。）

## 不做什么

- **不点「应用」**：那是唯一会重写宿主包的入口（解开 `app.asar`、打 66 个 app 平面补丁、
  把 asar 改名）。`autoApplyOnStart: false` 时启动路径是 `skip:boot-no-host-write`。
  ⚠️ 0.2.1 额外理由：那 66 个补丁的 `pattern` 字符串是按 **0.2.0-rc.2 源码**写的，
  在 0.2.1 上大概率大面积 `not found`——点了不但没用，还会重新解包/换包。
- 不挂 `dsh-purge/redteam`(index)：它会把官方预设落到 `$DSH_HOME/.agent-presets/redteam/`，
  与 dsh-agent-studio 管的同名 `redteam` 预设冲突（历史事故：
  `~/.dsh/redteam/preset-declare.json` 里的 `"error": "Duplicate agent preset: redteam"`）。
- 不动 `dsh.profile.bundles`、不动插件市场开关。

## 一个容易踩的落差：三条行不都走这份 fork

预设里只有 **`purge-core`** 指向 fork 的绝对路径。另外两行用的是**裸包名**：

```yaml
- id: redteam-store   name: dsh-purge/redteam/store    # → 解析到已安装副本
- id: redteam-tools   name: dsh-purge/redteam/tools    # → 解析到已安装副本
```

也就是 **store / tools 跑的是 `~/.dsh/profiles/desktop/node_modules/dsh-purge` 那份**，
不是这个 fork。目前两份的这些文件**逐字节相同**（差异只在 fork 的
`lib/index.js`、`lib/identity.js`、`package.json`、`presets/redteam/agent.cordis.yml`），
所以没有功能差异。

**但**：以后若只改 fork 的 `lib/redteam/*.js`，运行时**不会生效**。要改就把预设里那两行的
`name` 换成 fork 的绝对路径：

```yaml
- id: redteam-store
  name: /Users/cyberpsychosis/Dsh/dsh-purge-fork/lib/redteam/store.js
- id: redteam-tools
  name: /Users/cyberpsychosis/Dsh/dsh-purge-fork/lib/redteam/tools.js
```

（换完要 ⌘Q 重启。换成绝对路径后 `dsh.client` 扫描同样不会命中；子路径本来就不触发扫描。）

## 技能文件的 frontmatter 规则（0.2.1 实测）

`skills/redteam/*.md` 是**扁平文件**形态（`<root>/<name>.md`），0.2.1 仍把它和
`<name>/SKILL.md` 平级对待；扫描**只有一层**，别改成嵌套目录（`redteam/skills/recon/foo.md`
扫不到）。技能名取自 frontmatter 的 `name`，不是文件名。

| 字段 | 状态 |
|---|---|
| `name` | **必填**，且必须匹配 `^[a-z0-9]+(?:-[a-z0-9]+)*$` |
| `description` | **必填**，非空 |
| `whenToUse` | 可选（进 summary；模型目录只渲染 description） |
| `metadata` | 可选，任意 object |
| `disable-model-invocation` / `user-invocable` | 可选，严格布尔（kebab-case） |
| `role` / `enabled` | **宿主静默忽略**——纯注释，不是开关 |
| `modelInvocable` / `userInvocable` / `disableModelInvocation` | **硬拒**：出现即整条技能被丢弃（只留一条 warn） |

两条必须记住的：

1. **绝不要写 camelCase 的那三个旧键**。它们不是"被忽略"，而是让**整个技能文件消失**。
   要开关就用 kebab-case 反义键：`disable-model-invocation: true` / `user-invocable: false`。
2. **`enabled: false` 不会停用技能**（宿主不认这个字段）。真要让某个技能消失：删/移文件，
   或加 `disable-model-invocation: true`（只对模型隐藏）。

`role:` 同理只是留档（宿主和本插件的 `skill-availability.js` 都不读它）——角色分工靠
预设提示词，不靠技能文件筛选。

## 署名

本分支基于 [YuJunZhiXue/dsh-purge](https://github.com/YuJunZhiXue/dsh-purge)（MIT），
仅本地自用；上游 README 的署名与非商用要求继续适用。
