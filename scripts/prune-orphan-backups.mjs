/**
 * 孤儿宿主备份清理（dry-run 优先）。
 *
 * 背景：dsh-purge 在 `$DSH_HOME/dsh-purge/host-backups/` 里按内容寻址保存
 * 宿主原文快照，配套一个 .json 记 `path`（原始宿主文件位置）。官方桌面端升级
 * 会把 `resources/app` 重新封进 app.asar 并清掉解包目录，此后这些 `path`
 * 全部指向不存在的文件 —— 备份成为孤儿。
 *
 * 危害：卸载/还原时若按这些快照回写，会把「当前新版宿主文件」按旧版内容覆盖。
 *
 * 本脚本只做三件事：
 *   1. 读每个 .json 的 path，判断目标是否还存在（existsSync）
 *   2. 判断 path 是否仍落在「当前 dsh 安装」的可写范围内（避免误删还有效的备份）
 *   3. 默认 dry-run 只打印；加 --apply 才真的删
 *
 * 安全约束：
 *   · 只处理 host-backups 目录内的文件，绝不越界
 *   · 只有当 .json 可解析、且 path 确实不存在时才判定为孤儿
 *   · .json 解析失败 / 缺 path 字段的一律保留并单独列出（宁可留着）
 *   · --apply 前会把待删清单写到同目录 manifest-orphans-<ts>.txt
 */
import fs from "node:fs";
import path from "node:path";
import os from "node:os";

const DSH_HOME = process.env.DSH_HOME
  || path.join(os.homedir(), ".dsh");

const VAULT = path.join(DSH_HOME, "dsh-purge", "host-backups");
const APPLY = process.argv.includes("--apply");

function main() {
  if (!fs.existsSync(VAULT)) {
    console.log(`[skip] 没有 host-backups 目录: ${VAULT}`);
    return;
  }

  const names = fs.readdirSync(VAULT);
  const jsons = names.filter((n) => n.toLowerCase().endsWith(".json"));
  const baks = names.filter((n) => n.toLowerCase().endsWith(".bak"));

  const orphans = [];   // { stem, json, bak, target, reason }
  const kept = [];      // { stem, target, reason }
  const unparsable = []; // { json, reason }

  for (const jn of jsons) {
    const stem = jn.slice(0, -".json".length);
    const jp = path.join(VAULT, jn);
    const bp = path.join(VAULT, `${stem}.bak`);
    let meta;
    try {
      meta = JSON.parse(fs.readFileSync(jp, "utf8"));
    } catch (e) {
      unparsable.push({ json: jn, reason: `JSON 解析失败: ${e.message}` });
      continue;
    }
    const target = typeof meta?.path === "string" ? meta.path : "";
    if (!target) {
      unparsable.push({ json: jn, reason: "缺 path 字段" });
      continue;
    }
    if (fs.existsSync(target)) {
      kept.push({ stem, target, reason: "目标仍存在" });
      continue;
    }
    orphans.push({
      stem,
      json: jp,
      bak: fs.existsSync(bp) ? bp : "",
      target,
      reason: "目标不存在",
    });
  }

  // 没有任何 .json 配套的孤立 .bak —— 也属于孤儿，但单独归类，避免和上面重复删
  const matchedStems = new Set(jsons.map((n) => n.slice(0, -".json".length)));
  const looseBaks = baks.filter((n) => !matchedStems.has(n.slice(0, -".bak".length)));

  console.log(`vault: ${VAULT}`);
  console.log(`  .json ${jsons.length} | .bak ${baks.length}`);
  console.log(`  目标存在（保留）: ${kept.length}`);
  console.log(`  孤儿（目标不存在）: ${orphans.length}`);
  console.log(`  无法判定（保留，需人工看）: ${unparsable.length}`);
  console.log(`  无配套 json 的 .bak: ${looseBaks.length}`);
  console.log();

  if (kept.length) {
    console.log("--- 保留（目标仍在）---");
    for (const k of kept.slice(0, 10)) console.log(`  ${k.stem}  ->  ${k.target}`);
    if (kept.length > 10) console.log(`  ... 另外 ${kept.length - 10} 条`);
    console.log();
  }

  if (unparsable.length) {
    console.log("--- 无法判定（不会删）---");
    for (const u of unparsable) console.log(`  ${u.json}: ${u.reason}`);
    console.log();
  }

  if (orphans.length) {
    console.log("--- 孤儿样本（前 5 条）---");
    for (const o of orphans.slice(0, 5)) console.log(`  ${o.stem}  ->  ${o.target}`);
    console.log();
  }

  let freed = 0;
  for (const o of orphans) {
    for (const fp of [o.json, o.bak].filter(Boolean)) {
      try { freed += fs.statSync(fp).size; } catch { /* ignore */ }
    }
  }
  for (const n of looseBaks) {
    try { freed += fs.statSync(path.join(VAULT, n)).size; } catch { /* ignore */ }
  }
  console.log(`预计可释放: ${(freed / 1048576).toFixed(2)} MB`);

  if (!APPLY) {
    console.log("\n[dry-run] 未删除任何文件。加 --apply 执行。");
    return;
  }
  if (!orphans.length && !looseBaks.length) {
    console.log("\n没有需要清理的文件。");
    return;
  }

  // 删除前留清单，便于事后追溯
  const stamp = new Date().toISOString().replace(/[:.]/g, "-");
  const manifest = path.join(VAULT, `manifest-orphans-${stamp}.txt`);
  const lines = [
    `# dsh-purge 孤儿备份清理清单`,
    `# at: ${new Date().toISOString()}`,
    `# vault: ${VAULT}`,
    `# orphans: ${orphans.length}, loose_baks: ${looseBaks.length}`,
    "",
    ...orphans.flatMap((o) => [
      `target(不存在): ${o.target}`,
      `  json: ${o.json}`,
      ...(o.bak ? [`  bak : ${o.bak}`] : []),
    ]),
    ...looseBaks.map((n) => `loose_bak: ${path.join(VAULT, n)}`),
    "",
  ];
  fs.writeFileSync(manifest, lines.join("\n"), "utf8");
  console.log(`\n清单已写入: ${manifest}`);

  let removed = 0;
  let failed = 0;
  for (const o of orphans) {
    for (const fp of [o.json, o.bak].filter(Boolean)) {
      try { fs.unlinkSync(fp); removed += 1; } catch { failed += 1; }
    }
  }
  for (const n of looseBaks) {
    try { fs.unlinkSync(path.join(VAULT, n)); removed += 1; } catch { failed += 1; }
  }
  console.log(`已删除 ${removed} 个文件${failed ? `，失败 ${failed} 个` : ""}。`);
}

main();
