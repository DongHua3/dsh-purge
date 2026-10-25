/**
 * 确保 profile 的用户层里有 dsh-purge 本体条目。
 *
 * 背景（2026-10 实测）：
 *   dsh 0.2.1-rc.2 起，`profile.bundles` 不再自动为 bundle 建一个同名条目。
 *   旧版会自动入队 —— 那时的毛病是「再 insert 一次 = already queued: dsh-purge」
 *   （#152 / #154），所以老写法是在 bundle 层用 `- id: dsh-purge` 只改 inject/config。
 *
 *   现在 bundle 层那条 patch 永远匹配不到（dump-config 会打印
 *   `patch: entry "dsh-purge" not found`），本体条目根本不存在，后果是：
 *     · 宿主侧 apply() 不执行 → 破甲提示词、tools 全不注入
 *     · 客户端模块不加载 → 会话标题旁的 dsh-purge 按钮消失
 *
 * 做法：往用户层 `$DSH_HOME/profiles/<name>/cordis.patch.yml` 末尾追加一条
 * `- insert: [ {id: dsh-purge, ...} ]`。用户层在 bundle 层之后应用，所以能生效。
 *
 * 幂等：已经存在 `id: dsh-purge` 的 insert 就不动；文件里已有同名 insert 时跳过。
 * 安全：改之前先备份成 cordis.patch.yml.bak-<时间戳>。
 *
 * 用法：
 *   node scripts/ensure-profile-entry.mjs                 # 处理所有 profile
 *   node scripts/ensure-profile-entry.mjs desktop         # 只处理指定 profile
 *   node scripts/ensure-profile-entry.mjs --check         # 只检查，不写
 */
import fs from "node:fs";
import path from "node:path";
import os from "node:os";

const DSH_HOME = process.env.DSH_HOME || path.join(os.homedir(), ".dsh");
const PROFILES = path.join(DSH_HOME, "profiles");

const CHECK_ONLY = process.argv.includes("--check");
const args = process.argv.slice(2).filter((a) => !a.startsWith("--"));

const MARK = "# ── dsh-purge 本体（由 scripts/ensure-profile-entry.mjs 维护）";

const BODY = `
${MARK}
# 0.2.1-rc.2 起 profile.bundles 不再自动为 bundle 建条目，必须显式 insert 本体。
# 校验：dsh --profile <name> --dump-config | grep '^- id: dsh-purge$'
- insert:
    - id: dsh-purge
      name: dsh-purge
      inject: [systemPrompt, tools]
      config:
        enabled: true
        autoApplyOnStart: false
        autoUpdateOnStart: false
        autoRevertOnMissing: false
        injectOnce: false
        stripMnemon: true
        verbose: false
        postPrompt: ""
        postPromptOrder: 5100
        autoRetry: true
        retryMax: 3
        autoContinue: false
        continueMax: 3
        continueText: "继续"
        capabilityProtocol: true
        hooksDenyBypass: true
`;

/** 该 profile 是否需要（且有资格）拥有本体条目。 */
function profileWantsBundle(dir) {
  const pkgPath = path.join(dir, "package.json");
  if (!fs.existsSync(pkgPath)) return { ok: false, why: "无 package.json" };
  let pkg;
  try {
    pkg = JSON.parse(fs.readFileSync(pkgPath, "utf8"));
  } catch (e) {
    return { ok: false, why: `package.json 解析失败: ${e.message}` };
  }
  const bundles = pkg?.dsh?.profile?.bundles;
  if (!Array.isArray(bundles)) return { ok: false, why: "无 dsh.profile.bundles" };
  if (!bundles.includes("dsh-purge")) return { ok: false, why: "bundles 未声明 dsh-purge" };
  return { ok: true };
}

/** 用户层里是否已经写了本体（insert 或直接 - id: dsh-purge）。 */
function alreadyHasEntry(patchPath) {
  if (!fs.existsSync(patchPath)) return false;
  const text = fs.readFileSync(patchPath, "utf8");
  // 只要有 id: dsh-purge 的行就算有（insert 里的、或 patch 目标都行）
  return /^\s*-\s*id:\s*dsh-purge\s*$/m.test(text);
}

function processProfile(name) {
  const dir = path.join(PROFILES, name);
  if (!fs.existsSync(dir)) return { name, action: "skip", why: "目录不存在" };

  const want = profileWantsBundle(dir);
  if (!want.ok) return { name, action: "skip", why: want.why };

  const patchPath = path.join(dir, "cordis.patch.yml");
  if (alreadyHasEntry(patchPath)) return { name, action: "ok", why: "已有本体条目" };

  if (CHECK_ONLY) return { name, action: "need", why: "缺本体条目" };

  // 备份
  if (fs.existsSync(patchPath)) {
    const stamp = new Date().toISOString().replace(/[:.]/g, "-");
    fs.copyFileSync(patchPath, `${patchPath}.bak-${stamp}`);
  }
  const prev = fs.existsSync(patchPath) ? fs.readFileSync(patchPath, "utf8") : "";
  // 空文件或 `[]`（空 flow sequence）不能直接追加块序列 ——
  // `[]` 后面跟 `- insert:` 是非法 YAML（expected '<document start>'）。
  // 这两种情况直接写成块序列，其余情况保留原文并在末尾接一段。
  const bare = prev.trim();
  const next = bare === "" || bare === "[]"
    ? BODY.replace(/^\n/, "")
    : `${prev}${prev.endsWith("\n") ? "" : "\n"}${BODY}`;
  fs.writeFileSync(patchPath, next, "utf8");
  return { name, action: "written", why: bare === "[]" || bare === "" ? "已写入本体 insert（原文件为空）" : "已追加本体 insert" };
}

function main() {
  if (!fs.existsSync(PROFILES)) {
    console.log(`[skip] 没有 profiles 目录: ${PROFILES}`);
    return;
  }
  const names = args.length ? args : fs.readdirSync(PROFILES).filter((n) => {
    try { return fs.statSync(path.join(PROFILES, n)).isDirectory(); } catch { return false; }
  });

  let changed = 0;
  for (const name of names) {
    const r = processProfile(name);
    const tag = { ok: "✓", written: "✎", need: "!", skip: "·" }[r.action] || "?";
    console.log(`  ${tag} ${name.padEnd(18)} ${r.why}`);
    if (r.action === "written") changed += 1;
  }
  if (CHECK_ONLY) {
    console.log(changed ? "" : "\n(只检查，未写入)");
  } else if (changed) {
    console.log(`\n已更新 ${changed} 个 profile。重启宿主后生效。`);
  } else {
    console.log("\n无需改动。");
  }
}

// postinstall 会调这个脚本。任何意外都不能让安装失败 —— 拿不到 profile 就静默跳过。
try {
  main();
} catch (e) {
  console.log(`[skip] ensure-profile-entry: ${e && e.message ? e.message : e}`);
}
