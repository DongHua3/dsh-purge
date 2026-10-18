#!/usr/bin/env node
/**
 * 把本包自带的 paper-autopilot 技能装进当前宿主的官方技能目录。
 *
 * 只做两件事：定位 $DSH_HOME，把 skills/paper-autopilot 复制到 $DSH_HOME/skills/paper-autopilot。
 * 不改 profile、不动其它技能目录、不写任何全局配置。同名目录已存在时先备份为 <id>.bak-<时间戳>。
 *
 * 用法：
 *   node scripts/install-paper-autopilot.mjs              # 安装
 *   node scripts/install-paper-autopilot.mjs --dry-run    # 只打印将做什么
 *   node scripts/install-paper-autopilot.mjs --dest D:\x  # 指定技能根（调试用）
 *   node scripts/install-paper-autopilot.mjs --json       # 机器可读输出
 *
 * 装完无需重启：DSH 的文件监视器会加载新技能目录。
 */
import { promises as fsp } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { findDshHome } from "../lib/core.js";

const SKILL_ID = "paper-autopilot";
const SRC = fileURLToPath(new URL(`../skills/${SKILL_ID}/`, import.meta.url));

function argsOf(argv) {
  const out = { dryRun: false, json: false, dest: "" };
  for (let i = 0; i < argv.length; i += 1) {
    const a = argv[i];
    if (a === "--dry-run" || a === "-n") out.dryRun = true;
    else if (a === "--json") out.json = true;
    else if (a === "--dest") out.dest = String(argv[(i += 1)] || "");
    else if (a === "--help" || a === "-h") out.help = true;
  }
  return out;
}

function stamp() {
  const d = new Date();
  const p = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}${p(d.getHours())}${p(d.getMinutes())}${p(d.getSeconds())}`;
}

async function statTree(root) {
  let files = 0;
  let bytes = 0;
  const walk = async (dir) => {
    const entries = await fsp.readdir(dir, { withFileTypes: true });
    for (const e of entries) {
      const fp = path.join(dir, e.name);
      if (e.isDirectory()) await walk(fp);
      else if (e.isFile()) {
        files += 1;
        bytes += (await fsp.stat(fp)).size;
      }
    }
  };
  await walk(root);
  return { files, bytes };
}

async function main() {
  const opts = argsOf(process.argv.slice(2));
  if (opts.help) {
    console.log("用法：node scripts/install-paper-autopilot.mjs [--dry-run] [--dest <技能根>] [--json]");
    return 0;
  }

  const srcStat = await fsp.stat(SRC).catch(() => null);
  if (!srcStat || !srcStat.isDirectory()) {
    console.error(`[ERROR] 找不到本包技能目录：skills/${SKILL_ID}/（npm 包是否漏发了 skills？）`);
    return 1;
  }
  const skillMd = await fsp.stat(path.join(SRC, "SKILL.md")).catch(() => null);
  if (!skillMd) {
    console.error(`[ERROR] skills/${SKILL_ID}/SKILL.md 不存在，拒绝安装`);
    return 1;
  }

  const dshHome = findDshHome();
  const destRoot = opts.dest ? path.resolve(opts.dest) : path.join(dshHome, "skills");
  const dest = path.join(destRoot, SKILL_ID);
  const { files, bytes } = await statTree(SRC);

  const exists = Boolean(await fsp.stat(dest).catch(() => null));
  const backup = exists ? `${dest}.bak-${stamp()}` : "";

  const report = {
    ok: true,
    dryRun: opts.dryRun,
    dshHome,
    dest,
    files,
    bytes,
    overwrite: exists,
    backup,
  };

  if (opts.dryRun) {
    if (opts.json) console.log(JSON.stringify(report, null, 2));
    else {
      console.log(`[dry-run] 源      ：skills/${SKILL_ID}/（${files} 文件 / ${(bytes / 1024).toFixed(1)} KB）`);
      console.log(`[dry-run] 目标    ：${dest}`);
      console.log(`[dry-run] 覆盖    ：${exists ? `是，旧目录备份为 ${path.basename(backup)}` : "否（新增）"}`);
    }
    return 0;
  }

  await fsp.mkdir(destRoot, { recursive: true });
  if (exists) await fsp.rename(dest, backup);
  await fsp.cp(SRC, dest, { recursive: true });

  const after = await fsp.stat(path.join(dest, "SKILL.md")).catch(() => null);
  if (!after) {
    console.error("[ERROR] 复制后缺少 SKILL.md，安装失败");
    return 1;
  }

  if (opts.json) console.log(JSON.stringify(report, null, 2));
  else {
    console.log("==========================================================");
    console.log(`已安装技能  : ${SKILL_ID}`);
    console.log(`技能根      : ${destRoot}`);
    console.log(`文件/体积   : ${files} 个 / ${(bytes / 1024).toFixed(1)} KB`);
    if (exists) console.log(`旧目录备份  : ${path.basename(backup)}`);
    console.log("未触碰      : 技能根下其它技能目录；未修改任何全局配置");
    console.log("下一步      : 无需重启，DSH 文件监视器会加载；说「帮我写论文」或敲 /paper 触发");
    console.log("==========================================================");
  }
  return 0;
}

process.exitCode = await main();
