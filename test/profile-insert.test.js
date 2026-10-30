import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import {
  parseAllowBuildLine,
  formatAllowBuildLine,
  validateAllowBuildRewrite,
  purgePnpmBuildSpecs,
  rewritePnpmAllowBuilds,
  ensurePnpmAllowBuild,
  ensureProfileBodyInsert,
  classifyPatchBody,
  INSERT_BLOCK,
} from "../lib/profile-insert.js";

const MASTER_URL = "https://codeload.github.com/YuJunZhiXue/dsh-purge/tar.gz/refs/heads/master";
const COMMIT_URL = "https://codeload.github.com/YuJunZhiXue/dsh-purge/tar.gz/abc1234567890";

function withTempProfile(lockText) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "dsh-purge-test-"));
  if (lockText !== undefined) {
    fs.writeFileSync(path.join(dir, "pnpm-lock.yaml"), lockText, "utf8");
  }
  return dir;
}

function withTempPatch(content) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "dsh-purge-patch-"));
  if (content !== undefined) {
    fs.writeFileSync(path.join(dir, "cordis.patch.yml"), content, "utf8");
  }
  return dir;
}

/** 去掉注释和空行后，统计顶层 `- insert:` 组数（判定是不是第二个文档）。 */
function topLevelInsertGroups(text) {
  const lines = String(text || "").split(/\r?\n/);
  let count = 0;
  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    if (/^-\s*insert:\s*$/.test(line)) count += 1;
  }
  return count;
}

test("URL 键解析不被冒号截断", () => {
  const parsed = parseAllowBuildLine(`  dsh-purge@${MASTER_URL}: true`);
  assert.equal(parsed.key, `dsh-purge@${MASTER_URL}`);
  assert.equal(parsed.value, "true");
});

test("畸形键也解析成整键（自愈时统一丢弃）", () => {
  assert.deepEqual(parseAllowBuildLine("  dsh-purge@https: true"), {
    key: "dsh-purge@https",
    value: "true",
  });
  assert.deepEqual(parseAllowBuildLine("  dsh-purge@1.1.81: true"), {
    key: "dsh-purge@1.1.81",
    value: "true",
  });
});

test("行尾没有值的 `key:` 解析为空值", () => {
  assert.deepEqual(parseAllowBuildLine("  dsh-purge@https:"), {
    key: "dsh-purge@https",
    value: "",
  });
  assert.deepEqual(parseAllowBuildLine("  dsh-purge:"), {
    key: "dsh-purge",
    value: "",
  });
});

test("引号包裹的键照旧解析", () => {
  const spec = `dsh-purge@${MASTER_URL}`;
  for (const line of [`  "${spec}": true`, `  '${spec}': true`]) {
    assert.deepEqual(parseAllowBuildLine(line), { key: spec, value: "true" });
  }
});

test("URL 键写回带引号且 round-trip 无损", () => {
  const spec = `dsh-purge@${MASTER_URL}`;
  const line = formatAllowBuildLine(spec);
  assert.equal(line, `  "${spec}": true`);
  assert.deepEqual(parseAllowBuildLine(line), { key: spec, value: "true" });
  // 不含 URL 的键保持无引号，round-trip 同样无损
  const plain = formatAllowBuildLine("dsh-purge");
  assert.equal(plain, "  dsh-purge: true");
  assert.deepEqual(parseAllowBuildLine(plain), { key: "dsh-purge", value: "true" });
});

test("污染的 allowBuilds 重写后只剩期望键", () => {
  const polluted = [
    "packages:",
    "  - '.'",
    "",
    "allowBuilds:",
    "  cpu-features: true",
    "  ssh2: true",
    "  dsh-purge: true",
    "  dsh-purge@1.1.81: true",
    "  dsh-purge@https: true",
    "  dsh-purge@https: true",
    `  dsh-purge@${MASTER_URL}: true`,
    "",
  ].join("\n");
  const next = rewritePnpmAllowBuilds(polluted);
  const keys = next.split("\n").filter((line) => parseAllowBuildLine(line)).map((line) => parseAllowBuildLine(line).key);
  // 期望键：只有裸包名（#185，不再写 URL 键）
  const wanted = ["cpu-features", "ssh2", ...purgePnpmBuildSpecs()];
  assert.deepEqual([...new Set(keys)], wanted);
  // 畸形历史键一个都不留
  for (const bad of [`dsh-purge@1.1.81`, `dsh-purge@https`]) {
    assert.equal(keys.includes(bad), false, `should drop ${bad}`);
  }
  // 重复出现过的 `dsh-purge@https` 只允许来自 wanted 精确键，且不重复
  assert.equal(keys.filter((key) => key.startsWith("dsh-purge")).length, purgePnpmBuildSpecs().length);
  // 保留段的结构仍然合法
  assert.equal(validateAllowBuildRewrite(next), true);
});

test("非 purge 键原样保留，无 allowBuilds 段时追加", () => {
  const base = "packages:\n  - '.'\n";
  const next = rewritePnpmAllowBuilds(base);
  assert.equal(next.startsWith("packages:\n  - '.'\n\nallowBuilds:\n"), true);
  // 追加的是期望键（裸包名 + package.json 的 tarball）
  for (const spec of purgePnpmBuildSpecs()) {
    const escaped = formatAllowBuildLine(spec).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    assert.match(next, new RegExp(`^${escaped}$`, "m"));
  }
  const withSection = "allowBuilds:\n  cpu-features: true\n  ssh2: true\n";
  const next2 = rewritePnpmAllowBuilds(withSection);
  assert.match(next2, /^ {2}cpu-features: true$/m);
  assert.match(next2, /^ {2}ssh2: true$/m);
});

test("写前校验：重复顶层键 / 重复 allowBuilds 键 / 解析不了的行判无效", () => {
  assert.equal(validateAllowBuildRewrite("packages:\n  - '.'\n\npackages:\n  - \"..\"\n"), false);
  assert.equal(validateAllowBuildRewrite("allowBuilds:\n  cpu-features: true\n  cpu-features: true\n"), false);
  // 没有键值分隔的裸行解析不出来，校验必须挡下
  assert.equal(validateAllowBuildRewrite("allowBuilds:\n  不是键值对\n"), false);
  assert.equal(validateAllowBuildRewrite("allowBuilds:\n# 注释行放行\n  ssh2: true\n"), true);
});

test("期望键只有裸包名，不含任何 URL 键（#185）", () => {
  // pnpm 11 遇到 `dsh-purge@https://...` 会报 ERR_PNPM_INVALID_VERSION_UNION，
  // allowBuilds 按包名匹配即可，tarball / git / registry 安装都放行
  assert.deepEqual(purgePnpmBuildSpecs(), ["dsh-purge"]);
  const dir = withTempProfile([
    "lockfileVersion: '9.0'",
    "",
    "importers:",
    "",
    "  .:",
    "    dependencies:",
    "      dsh-purge:",
    `        specifier: ${COMMIT_URL}`,
    `        version: dsh-purge@${COMMIT_URL}`,
    "",
  ].join("\n"));
  assert.deepEqual(purgePnpmBuildSpecs(dir), ["dsh-purge"]);
});

test("输入只含 URL 键时重写后只剩裸包名", () => {
  const onlyUrl = [
    "allowBuilds:",
    `  "dsh-purge@${MASTER_URL}": true`,
    `  dsh-purge@${MASTER_URL}: true`,
    "",
  ].join("\n");
  const next = rewritePnpmAllowBuilds(onlyUrl);
  const keys = next.split("\n").filter((line) => parseAllowBuildLine(line)).map((line) => parseAllowBuildLine(line).key);
  assert.deepEqual(keys, ["dsh-purge"]);
  assert.equal(next.includes("dsh-purge@"), false);
  assert.equal(next.split("\n").some((line) => line === "  dsh-purge: true"), true);
  assert.equal(validateAllowBuildRewrite(next), true);
});

test("固定 commit 安装：重写后只剩裸包名，历史 URL / 畸形键全清", () => {
  const dir = withTempProfile([
    "lockfileVersion: '9.0'",
    "",
    "importers:",
    "",
    "  .:",
    "    dependencies:",
    "      dsh-purge:",
    `        specifier: ${COMMIT_URL}`,
    `        version: dsh-purge@${COMMIT_URL}`,
    "",
  ].join("\n"));
  const polluted = [
    "packages:",
    "  - '.'",
    "",
    "allowBuilds:",
    "  ssh2: true",
    `  dsh-purge@${MASTER_URL}: true`,
    `  "dsh-purge@${COMMIT_URL}": true`,
    "  dsh-purge@https: true",
    "",
  ].join("\n");
  const next = rewritePnpmAllowBuilds(polluted, dir);
  const keys = next.split("\n").filter((line) => parseAllowBuildLine(line)).map((line) => parseAllowBuildLine(line).key);
  assert.equal(keys.includes("dsh-purge"), true);
  assert.equal(keys.includes(`dsh-purge@${COMMIT_URL}`), false);
  assert.equal(keys.includes(`dsh-purge@${MASTER_URL}`), false);
  assert.equal(keys.includes("dsh-purge@https"), false);
  assert.equal(keys.includes("ssh2"), true);
  // 只写裸包名，不带引号
  assert.equal(next.split("\n").some((line) => line === "  dsh-purge: true"), true);
});

test("幂等：健康文件重写输出等于输入，零写入", () => {
  const dir = withTempProfile();
  const fp = path.join(dir, "pnpm-workspace.yaml");
  const healthy = [
    "packages:",
    "  - '.'",
    "",
    "allowBuilds:",
    "  cpu-features: true",
    "  ssh2: true",
    "  dsh-purge: true",
    "",
  ].join("\n");
  fs.writeFileSync(fp, healthy, "utf8");
  const before = fs.readFileSync(fp, "utf8");
  assert.equal(rewritePnpmAllowBuilds(before, dir), before);
  const statBefore = fs.statSync(fp);
  const result = ensurePnpmAllowBuild(dir);
  assert.equal(result.wrote, false);
  assert.equal(result.ok, true);
  assert.equal(fs.readFileSync(fp, "utf8"), before);
  assert.equal(fs.statSync(fp).mtimeMs, statBefore.mtimeMs);
});

test("幂等：第二次 ensure 不再写盘（自愈后收敛）", () => {
  const dir = withTempProfile();
  const fp = path.join(dir, "pnpm-workspace.yaml");
  const polluted = `allowBuilds:\n  ssh2: true\n  dsh-purge@https: true\n  dsh-purge@1.1.81: true\n`;
  fs.writeFileSync(fp, polluted, "utf8");
  const first = ensurePnpmAllowBuild(dir);
  assert.equal(first.wrote, true);
  const healed = fs.readFileSync(fp, "utf8");
  // 畸形历史键被清掉
  assert.equal(healed.includes("dsh-purge@https"), false);
  assert.equal(healed.includes("dsh-purge@1.1.81"), false);
  // 只剩裸包名
  assert.equal(healed.includes("  dsh-purge: true"), true);
  const second = ensurePnpmAllowBuild(dir);
  assert.equal(second.wrote, false);
  assert.equal(fs.readFileSync(fp, "utf8"), healed);
});

// ---- #191：cordis.patch.yml 是 `[]` 时追加会导致宿主启动解析失败 ----

test("patch 形态分类：空 / 空 flow / 块序列 / 非空 flow / 未知", () => {
  assert.equal(classifyPatchBody("").kind, "empty");
  assert.equal(classifyPatchBody("# 只有注释\n\n").kind, "empty");
  assert.equal(classifyPatchBody("[]").kind, "empty-flow");
  assert.equal(classifyPatchBody("# c\n[]\n").kind, "empty-flow");
  assert.equal(classifyPatchBody("---\n[]\n").kind, "empty-flow");
  assert.equal(classifyPatchBody("- id: foo\n  name: foo\n").kind, "block-seq");
  assert.equal(classifyPatchBody("[a, b]\n").kind, "flow-seq");
  assert.equal(classifyPatchBody("foo: bar\n").kind, "unknown");
});

test("空文件：直接写 insert 块", () => {
  const dir = withTempPatch(undefined);
  const fp = path.join(dir, "cordis.patch.yml");
  const result = ensureProfileBodyInsert(dir);
  assert.equal(result.ok, true);
  assert.equal(result.wrote, true);
  assert.equal(fs.readFileSync(fp, "utf8"), INSERT_BLOCK);
});

test("只有注释和空行：写 insert 块，注释保留", () => {
  const dir = withTempPatch("# overrides, disables, and insertions\n\n");
  const fp = path.join(dir, "cordis.patch.yml");
  const result = ensureProfileBodyInsert(dir);
  assert.equal(result.ok, true);
  assert.equal(result.wrote, true);
  const text = fs.readFileSync(fp, "utf8");
  assert.equal(text.includes("# overrides, disables, and insertions"), true);
  assert.equal(text.includes("- insert:"), true);
  assert.equal(topLevelInsertGroups(text), 1);
});

test("注释 + `[]`：`[]` 被替换成 insert 块，注释保留，无第二个文档", () => {
  const dir = withTempPatch("# overrides, disables, and insertions\n[]\n");
  const fp = path.join(dir, "cordis.patch.yml");
  const result = ensureProfileBodyInsert(dir);
  assert.equal(result.ok, true);
  assert.equal(result.wrote, true);
  const text = fs.readFileSync(fp, "utf8");
  assert.equal(text.includes("[]"), false);
  assert.equal(text.includes("# overrides, disables, and insertions"), true);
  assert.equal(text.includes("- insert:"), true);
  // 只有一个顶层 `- insert:` 组 → 没有变成第二个文档
  assert.equal(topLevelInsertGroups(text), 1);
});

test("`---` 前缀 + `[]`：同样替换，无第二个文档", () => {
  const dir = withTempPatch("---\n[]\n");
  const fp = path.join(dir, "cordis.patch.yml");
  const result = ensureProfileBodyInsert(dir);
  assert.equal(result.ok, true);
  assert.equal(result.wrote, true);
  const text = fs.readFileSync(fp, "utf8");
  assert.equal(text.includes("[]"), false);
  assert.equal(topLevelInsertGroups(text), 1);
});

test("正常块序列：沿用旧的追加行为", () => {
  const original = "- id: foo\n  name: foo\n";
  const dir = withTempPatch(original);
  const fp = path.join(dir, "cordis.patch.yml");
  const result = ensureProfileBodyInsert(dir);
  assert.equal(result.ok, true);
  assert.equal(result.wrote, true);
  const text = fs.readFileSync(fp, "utf8");
  assert.equal(text.startsWith(original), true);
  assert.equal(text.includes("- insert:"), true);
  assert.equal(topLevelInsertGroups(text), 1);
});

test("非空 flow 序列：宿主内容不动，返回 ok:false", () => {
  const original = "[a, b]\n";
  const dir = withTempPatch(original);
  const fp = path.join(dir, "cordis.patch.yml");
  const result = ensureProfileBodyInsert(dir);
  assert.equal(result.ok, false);
  assert.equal(result.wrote, false);
  assert.equal(fs.readFileSync(fp, "utf8"), original);
});

test("已有 dsh-purge 本体行：零写入", () => {
  const original = "- insert:\n    - id: dsh-purge\n      name: dsh-purge\n";
  const dir = withTempPatch(original);
  const fp = path.join(dir, "cordis.patch.yml");
  const result = ensureProfileBodyInsert(dir);
  assert.equal(result.ok, true);
  assert.equal(result.wrote, false);
  assert.equal(fs.readFileSync(fp, "utf8"), original);
});

test("`[]` 替换后幂等：再 ensure 一次零写入", () => {
  const dir = withTempPatch("# c\n[]\n");
  const fp = path.join(dir, "cordis.patch.yml");
  const first = ensureProfileBodyInsert(dir);
  assert.equal(first.wrote, true);
  const healed = fs.readFileSync(fp, "utf8");
  const second = ensureProfileBodyInsert(dir);
  assert.equal(second.wrote, false);
  assert.equal(fs.readFileSync(fp, "utf8"), healed);
});