/**
 * 一键发布：校验 → commit → merge → push master → 打 annotated tag → 推送。
 *
 * 为什么要这个脚本：
 *   本仓库的 Actions「branch push」事件在 GitHub 侧没有注册成功（建仓时历史被重写，
 *   runs 一直是 0）。现在 workflow 同时监听 `v*` tag 推送，所以推 tag 能触发 CI；
 *   脚本把「tag 必须指向 master 最新 commit」这条约束固化下来，避免发错。
 *
 * 用法：
 *   node scripts/release.mjs --dry-run        # 只校验 + 打印将要做什么
 *   node scripts/release.mjs                  # 真跑
 *   node scripts/release.mjs --no-tag         # 只 push master，不打 tag
 *
 * 前置：
 *   package.json 的 version 与 release-notes.md 第一行 `# <version>` 必须一致
 *   （CI 也会校验，这里提前失败，省一次跑 CI 的时间）
 *
 * 安全：
 *   · 任何一步失败立即停止，不继续往下推
 *   · tag 已存在且指向不同 commit 时拒绝（避免强推覆盖历史）
 *   · 不在 master 分支时拒绝
 */
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

const ROOT = execFileSync("git", ["rev-parse", "--show-toplevel"], { encoding: "utf8" }).trim();
process.chdir(ROOT);

const DRY = process.argv.includes("--dry-run");
const NO_TAG = process.argv.includes("--no-tag");

const C = { red: "\x1b[31m", green: "\x1b[32m", yellow: "\x1b[33m", dim: "\x1b[2m", reset: "\x1b[0m" };
const info = (m) => console.log(m);
const ok = (m) => console.log(`${C.green}✓${C.reset} ${m}`);
const warn = (m) => console.log(`${C.yellow}!${C.reset} ${m}`);
const die = (m) => { console.error(`${C.red}✗ ${m}${C.reset}`); process.exit(1); };

function git(args, opts = {}) {
  // stdio: "inherit" 时 execFileSync 返回 null，不能无条件 .trim()
  const out = execFileSync("git", args, { encoding: "utf8", stdio: opts.inherit ? "inherit" : "pipe", ...opts });
  return out == null ? "" : String(out).trim();
}

function sh(cmd, args, opts = {}) {
  const out = execFileSync(cmd, args, { encoding: "utf8", stdio: opts.inherit ? "inherit" : "pipe", ...opts });
  return out == null ? "" : String(out).trim();
}

// ---------- 1. 前置校验 ----------
info(`${C.dim}repo: ${ROOT}${C.reset}`);

const branch = git(["rev-parse", "--abbrev-ref", "HEAD"]);
if (branch !== "master") die(`当前在 "${branch}"，发布必须在 master 上。`);

const pkg = JSON.parse(fs.readFileSync(path.join(ROOT, "package.json"), "utf8"));
const version = String(pkg.version || "");
if (!version) die("package.json 读不到 version。");

const notesFirst = fs.readFileSync(path.join(ROOT, "release-notes.md"), "utf8")
  .split(/\r?\n/, 1)[0].trim();
if (notesFirst !== `# ${version}`) {
  die(`release-notes.md 第一行必须是 "# ${version}"，现在是 "${notesFirst}"。`);
}
ok(`version ${version}，release-notes 匹配`);

const dirty = git(["status", "--porcelain"]);
if (dirty) die(`工作区不干净，先提交或 stash：\n${dirty}`);
ok("工作区干净");

// 本地是否落后远端
git(["fetch", "origin", "master", "--quiet"]);
const behind = git(["rev-list", "--count", "HEAD..origin/master"]);
if (Number(behind) > 0) die(`本地 master 落后 origin/master ${behind} 个 commit，先 pull。`);
ok("与 origin/master 同步或领先");

// ---------- 2. 语法与测试（和 CI 一致的那几条）----------
const checks = [
  ["node", ["--check", "lib/index.js"]],
  ["node", ["--check", "lib/core.js"]],
  ["node", ["--check", "lib/reapply.js"]],
];
for (const [cmd, args] of checks) {
  try { sh(cmd, args); } catch (e) { die(`语法检查失败: node ${args.join(" ")}\n${e.stderr || e.message}`); }
}
try {
  sh("node", ["--input-type=module", "-e", "import './lib/index.js'"]);
} catch (e) {
  die(`import 冒烟失败:\n${e.stderr || e.message}`);
}
ok("语法 + import 冒烟通过");

// notes 截取（与 workflow 同一套逻辑）
const allNotes = fs.readFileSync(path.join(ROOT, "release-notes.md"), "utf8");
const sections = allNotes.split(/\n(?=# 1\.1\.)/);
const mine = sections.find((p) => p.trimStart().startsWith(`# ${version}`));
if (!mine) die(`release-notes.md 里找不到 "# ${version}" 段落。`);
const sectionCount = (mine.match(/^# 1\.1\./gm) || []).length;
if (sectionCount !== 1) die(`截取出来的段落含 ${sectionCount} 个版本标题，应该只有 1 个。`);
ok(`release notes 截取 ${mine.trim().length} 字符，只含当前版本`);

// ---------- 3. 是否已有 tag ----------
const tag = `v${version}`;
let tagExists = false;
try { git(["rev-parse", "-q", "--verify", `refs/tags/${tag}`]); tagExists = true; } catch { tagExists = false; }
const headSha = git(["rev-parse", "HEAD"]);

if (tagExists) {
  const tagSha = git(["rev-parse", `${tag}^{commit}`]);
  if (tagSha !== headSha) {
    die(`tag ${tag} 已存在且指向 ${tagSha.slice(0, 7)}，当前 HEAD 是 ${headSha.slice(0, 7)}。\n`
      + `  要重发请显式删除后重来: git tag -d ${tag} && git push origin :refs/tags/${tag}`);
  }
  warn(`tag ${tag} 已存在且指向 HEAD（可复用）`);
}

// ---------- 4. 计划 ----------
const ahead = git(["rev-list", "--count", "origin/master..HEAD"]);
info("");
info("将执行：");
info(`  1) git push origin master${Number(ahead) > 0 ? `   (${ahead} 个新 commit)` : "   (已是最新)"}`);
if (!NO_TAG) {
  info(`  2) git tag -a ${tag} -m "${tag}"   →  ${headSha.slice(0, 7)}`);
  info(`  3) git push origin ${tag}`);
  info(`  4) 调 workflow_dispatch 触发 CI（本仓库 push 事件不触发，见文件头说明）`);
  info(`  5) 轮询 Release 直到出现`);
} else {
  info(`  2) (跳过 tag 与 CI)`);
}
info("");

if (DRY) {
  info(`${C.yellow}[dry-run] 未做任何修改。${C.reset}`);
  process.exit(0);
}

// ---------- 5. 执行 ----------
info("→ push master");
git(["push", "origin", "master"], { inherit: true });
ok("master 已推送");

if (NO_TAG) {
  info("\n完成（未打 tag）。");
  process.exit(0);
}

if (!tagExists) {
  git(["tag", "-a", tag, "-m", tag]);
  ok(`tag ${tag} 已创建`);
}
info(`→ push ${tag}`);
git(["push", "origin", tag], { inherit: true });
ok(`${tag} 已推送`);

// ---------- 6. 触发 CI 并等待 ----------
// 本仓库的 push 事件（branch 与 tag）在 GitHub Actions 侧都没注册成功，
// 只有 workflow_dispatch 有效，所以这里显式调一次 API。
const REPO = "DongHua3/dsh-purge";
const WORKFLOW_ID = "393558246";

function ghToken() {
  // 优先环境变量，其次 git credential fill（本机 GCM 里已有）
  if (process.env.GH_TOKEN) return process.env.GH_TOKEN;
  try {
    const out = execFileSync("git", ["credential", "fill"], {
      input: "protocol=https\nhost=github.com\n\n",
      encoding: "utf8",
    });
    const m = /^password=(.+)$/m.exec(out);
    return m ? m[1].trim() : "";
  } catch {
    return "";
  }
}

const token = ghToken();
if (!token) {
  warn("拿不到 GitHub token，跳过自动触发。请到 Actions 页面手动 Run workflow。");
  info(`  https://github.com/${REPO}/actions/workflows/release.yml`);
  process.exit(0);
}

async function gh(path, init = {}) {
  const res = await fetch(`https://api.github.com${path}`, {
    ...init,
    headers: {
      authorization: `Bearer ${token}`,
      accept: "application/vnd.github+json",
      "content-type": "application/json",
      "user-agent": "dsh-purge-release",
      ...(init.headers || {}),
    },
  });
  return res;
}

info("→ workflow_dispatch");
{
  const res = await gh(`/repos/${REPO}/actions/workflows/${WORKFLOW_ID}/dispatches`, {
    method: "POST",
    body: JSON.stringify({ ref: "master" }),
  });
  if (res.status !== 204) {
    warn(`dispatch 返回 HTTP ${res.status}，请手动触发。`);
    info(`  https://github.com/${REPO}/actions/workflows/release.yml`);
    process.exit(0);
  }
  ok("CI 已触发");
}

info("→ 等待 Release 出现（最多 5 分钟）");
let release = null;
for (let i = 0; i < 30; i += 1) {
  await new Promise((r) => setTimeout(r, 10000));
  const res = await gh(`/repos/${REPO}/releases/tags/${tag}`);
  if (res.status === 200) {
    release = await res.json();
    break;
  }
  process.stdout.write(".");
}
process.stdout.write("\n");

if (!release) {
  warn("5 分钟内没等到 Release。CI 可能仍在跑或失败：");
  info(`  https://github.com/${REPO}/actions`);
  process.exit(1);
}

const assets = release.assets || [];
ok(`Release 已生成: ${release.html_url}`);
info(`  资产: ${assets.map((a) => `${a.name} (${a.size}B)`).join(", ") || "(无)"}`);
info(`  正文: ${(release.body || "").length} 字符，首行 "${(release.body || "").split("\n")[0]}"`);

if (!assets.length) {
  warn("Release 里没有资产，检查 CI 的 upload 步骤。");
}

