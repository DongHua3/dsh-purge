#!/usr/bin/env node
// dsh-purge 回归测试：#40 形状覆盖 + hostFs 同步方法完整性 + 备份链路
// 用法: node scripts/check-40-and-hostfs.mjs
// 只读宿主，所有写操作都发生在 os.tmpdir() 的夹具里。
import fs from "node:fs";
import fsp from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const root = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const core = await import(pathToFileURL(path.join(root, "lib", "core.js")).href);
const ea = await import(pathToFileURL(path.join(root, "lib", "extract-asar.js")).href);

let failed = 0;
const check = (name, ok, extra = "") => {
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${extra ? `  ${extra}` : ""}`);
  if (!ok) failed += 1;
};

const p40 = core.ALL_PATCHES.find((p) => p.id === 40);
check("#40 存在且 variant >= 8（新增 0.2-rc.2 + 兜底）", Boolean(p40) && p40.replacements.length >= 8, `variants=${p40?.replacements.length}`);

// 1) 0.2.0-rc.2 形状
const rc2 = [
  "\tasync assemble(context = {}) {",
  '\t\tconst transformed = await this.ctx.waterfall(scopeTarget(this, scope), "system-prompt/assemble", assembly, context, () => Promise.resolve(assembly));',
  "\t\tif (completeSection === void 0 && !runtimeContextSuppressed) return transformed;",
  "\t\tconst requiredContexts = new Set([...contextByName.values()].filter((entry) => entry.required === true).map((entry) => entry.name));",
  "\t\treturn {",
  "\t\t\t...transformed,",
  "\t\t\tsections: completeSection === void 0 ? transformed.sections : [completeSection],",
  "\t\t\tcontexts: runtimeContextSuppressed ? transformed.contexts.filter((entry) => requiredContexts.has(entry.name)) : transformed.contexts",
  "\t\t};",
  "\t}",
].join("\n");

const r1 = core.applyReplacementsToText(rc2, p40, "host/dsh-system-prompt/lib/index.js");
check("rc.2 形状命中", r1.changed === true);
check("rc.2 写进 inject 标记", core.hostPromptKeepsInject(r1.text) === true);
check("rc.2 保留 requiredContexts 语义", r1.text.includes("const requiredContexts = new Set(") && r1.text.includes("requiredContexts.has(entry.name)"));
const r2 = core.applyReplacementsToText(r1.text, p40, "host/dsh-system-prompt/lib/index.js");
check("rc.2 幂等（二次 apply 不改文件）", r2.changed === false && r2.text === r1.text);

// 2) 未来形状：官方再换周边代码，只剩「complete 顶掉全部 section」那一句
const future = [
  "\tasync assemble(context = {}) {",
  "\t\tconst transformed = await this.ctx.waterfall(scopeTarget(this, scope), \"system-prompt/assemble\", assembly, context, () => Promise.resolve(assembly));",
  "\t\tif (completeSection === void 0 && !runtimeContextSuppressed) return transformed;",
  "\t\tconst unknownFutureHelper = 42;",
  "\t\treturn {",
  "\t\t\t...transformed,",
  "\t\t\tsections: completeSection === void 0 ? transformed.sections : [completeSection],",
  "\t\t\tcontexts: transformed.contexts",
  "\t\t};",
  "\t}",
].join("\n");
const f1 = core.applyReplacementsToText(future, p40, "host/dsh-system-prompt/lib/index.js");
check("未知新形状走兜底 pattern", f1.changed === true && core.hostPromptKeepsInject(f1.text) === true);
check("兜底不破坏周边代码", f1.text.includes("unknownFutureHelper = 42"));
const f2 = core.applyReplacementsToText(f1.text, p40, "host/dsh-system-prompt/lib/index.js");
check("兜底幂等", f2.changed === false && f2.text === f1.text);

// 3) hostFs 同步方法完整性（缺 closeSync 会让 backupAll 全量 EPERM）
for (const m of ["openSync", "closeSync", "readSync", "writeSync", "fsyncSync", "fstatSync", "lstatSync", "renameSync", "copyFileSync"]) {
  check(`hostFs.${m} 存在`, typeof ea.hostFs[m] === "function");
}

// 4) 备份链路：占位 + copy + rename-over-existing 必须在夹具里跑通
const fixture = await fsp.mkdtemp(path.join(os.tmpdir(), "dsh-purge-baktest-"));
const src = path.join(fixture, "index.js");
const dst = `${src}.dshpurge.bak`;
await fsp.writeFile(src, "// fixture\n", "utf8");
const fd = ea.hostFs.openSync(dst, "wx");
ea.hostFs.closeSync(fd);
const tmp = `${dst}.${process.pid}.${Date.now()}.copytmp`;
await ea.hostFs.promises.copyFile(src, tmp);
let renameOk = true;
try {
  await ea.hostFs.promises.rename(tmp, dst);
} catch (e) {
  renameOk = false;
  console.log(`       rename error: ${e.code} ${e.message.split("\n")[0]}`);
}
check("备份 rename 不再 EPERM", renameOk && fs.existsSync(dst));
await fsp.rm(fixture, { recursive: true, force: true });

// 5) desktop.js isOfficialHarnessExecutable 识别 DSH Desktop.exe 与同步备份
const desktop = await import(pathToFileURL(path.join(root, "lib", "desktop.js")).href);
check("isOfficialHarnessExecutable 识别 DSH Desktop.exe", desktop.isOfficialHarnessExecutable("C:\\Program Files\\DSH Desktop\\DSH Desktop.exe") === true);

// 6) redteam installPreset 自愈已落盘旧预设里的 toolFilter
const rt = await import(pathToFileURL(path.join(root, "lib", "redteam", "index.js")).href);
const oldHome = process.env.DSH_HOME;
const tmpHome = await fsp.mkdtemp(path.join(os.tmpdir(), "dsh-purge-rt-"));
try {
  process.env.DSH_HOME = tmpHome;
  const presetDir = path.join(tmpHome, ".agent-presets", "redteam");
  await fsp.mkdir(presetDir, { recursive: true });
  const legacyYml = [
    "- id: workflow-ptc",
    "  name: '@deepseek-ai/dsh-workflow-ptc'",
    "- id: tool-subagent",
    "  name: '@deepseek-ai/dsh-tool-subagent'",
    "  disabled: false",
    "  config:",
    "    maxDepth: 1",
    "    toolFilter:",
    "      deny:",
    "        - subagent_fork",
    "        - workflow",
    "        - ralph",
    "- id: redteam-tools",
    "  name: dsh-purge/redteam/tools",
  ].join("\n");
  await fsp.writeFile(path.join(presetDir, "agent.cordis.yml"), legacyYml, "utf8");
  const res = rt.installPreset({ force: false });
  const repairedYml = await fsp.readFile(path.join(presetDir, "agent.cordis.yml"), "utf8");
  check("redteam 旧预设自愈剥离 toolFilter", !repairedYml.includes("toolFilter:") && res.action === "repaired");
} finally {
  if (oldHome === undefined) delete process.env.DSH_HOME;
  else process.env.DSH_HOME = oldHome;
  await fsp.rm(tmpHome, { recursive: true, force: true });
}

// 7) identity.js installAssembleGuard 在原生 assemble 抛异常时仍执行 rewrite 保留破甲注入
const idMod = await import(pathToFileURL(path.join(root, "lib", "identity.js")).href);
const fakePrompt = {
  async assemble() {
    throw new Error("unknown prompt variable {{bad}}");
  },
};
idMod.installAssembleGuard(fakePrompt, (assembled) => idMod.rewritePromptAssembly(assembled, "INJECT_PAYLOAD_OK"));
const guardedOut = await fakePrompt.assemble({});
check("assembleGuard 原生异常时仍保留破甲注入", guardedOut.sections.some((s) => String(s?.text || "").includes("INJECT_PAYLOAD_OK")));

// 8) #45 / #46 / #93 desktop-shell 官方更新交接 CWD 解锁与跨版本升级幂等性
const p45 = core.ALL_PATCHES.find((p) => p.id === 45);
const p46 = core.ALL_PATCHES.find((p) => p.id === 46);
const p93 = core.ALL_PATCHES.find((p) => p.id === 93);
check("#45 / #46 / #93 均已注册", Boolean(p45 && p46 && p93));

const countOccurrences = (haystack, needle) => haystack.split(needle).length - 1;
const applyDesktopUpdateChain = (src) => {
  const s45 = core.applyReplacementsToText(src, p45, "desktop/lib/main.js");
  const s46 = core.applyReplacementsToText(s45.text, p46, "desktop/lib/main.js");
  const s93 = core.applyReplacementsToText(s46.text, p93, "desktop/lib/main.js");
  return { text: s93.text, c45: s45.changed, c46: s46.changed, c93: s93.changed };
};

const stockDesktopShell = [
  "var DesktopUpdateCoordinator = class {",
  "\tinstallAndRestart() {",
  "\t\t\t\tthis.updater.quitAndInstall(true, true);",
  "\t}",
  "};",
].join("\n");

const freshOut = applyDesktopUpdateChain(stockDesktopShell);
check("#45 全新宿主一次命中且 #46/#93 自动跳过", freshOut.c45 === true && freshOut.c46 === false && freshOut.c93 === false);
check("#45 注入 launchCwd + cd /d + start /D + spawn cwd", freshOut.text.includes("cwd: launchCwd") && freshOut.text.includes("start \\\"\\\" /D \\\"\" + launchCwd") && freshOut.text.includes("cd /d \\\"\" + launchCwd"));
check("#45 不依赖未导入的 os/tmpdir 标识符", !/\bos\.tmpdir\b|\btmpdir\s*\(/.test(freshOut.text));
check("#45 仅声明一次 dshPurgeWshLiteral / dshPurgeHandoffDesktopUpdate", countOccurrences(freshOut.text, "function dshPurgeWshLiteral(") === 1 && countOccurrences(freshOut.text, "function dshPurgeHandoffDesktopUpdate(") === 1);
const freshAgain = applyDesktopUpdateChain(freshOut.text);
check("#45/#46/#93 全新宿主二次执行完全幂等", !freshAgain.c45 && !freshAgain.c46 && !freshAgain.c93 && freshAgain.text === freshOut.text);

// 模拟 1.1.21–1.1.80 已打补丁的 desktop-shell（带 dshPurgeWshLiteral，无 launchCwd）
const legacy1180Shell = freshOut.text
  .replace(
    "\t\tconst launchCwd = process.env.TEMP || process.env.TMP || homedir();\n" +
    "\t\tconst script = join(launchCwd, \"dsh-purge-official-update.js\");\n" +
    "\t\tconst launcher = join(launchCwd, \"dsh-purge-official-update.cmd\");\n" +
    "\t\twriteFileSync(script, body, \"utf8\");\n" +
    "\t\twriteFileSync(launcher, \"@echo off\\r\\ncd /d \\\"\" + launchCwd + \"\\\"\\r\\nstart \\\"\\\" /D \\\"\" + launchCwd + \"\\\" wscript.exe //nologo //B \\\"\" + script + \"\\\"\\r\\n\", \"utf8\");\n" +
    "\t\tspawn(\"cmd.exe\", [\"/d\", \"/c\", launcher], { cwd: launchCwd, detached: true, stdio: \"ignore\", windowsHide: true }).unref();",
    "\t\tconst script = join(process.env.TEMP || \"\", \"dsh-purge-official-update.js\");\n" +
    "\t\tconst launcher = join(process.env.TEMP || \"\", \"dsh-purge-official-update.cmd\");\n" +
    "\t\twriteFileSync(script, body, \"utf8\");\n" +
    "\t\twriteFileSync(launcher, \"@echo off\\r\\nstart \\\"\\\" wscript.exe //nologo //B \\\"\" + script + \"\\\"\\r\\n\", \"utf8\");\n" +
    "\t\tspawn(\"cmd.exe\", [\"/d\", \"/c\", launcher], { detached: true, stdio: \"ignore\", windowsHide: true }).unref();"
  );
check("1.1.80 旧版夹具构造成功（不含 launchCwd）", !legacy1180Shell.includes("launchCwd"));
const up1180 = applyDesktopUpdateChain(legacy1180Shell);
check("#93 原地升级 1.1.21–1.1.80 宿主且不重复注入函数", up1180.c45 === false && up1180.c46 === false && up1180.c93 === true && up1180.text === freshOut.text);
const up1180Again = applyDesktopUpdateChain(up1180.text);
check("#93 升级后二次执行幂等", !up1180Again.c45 && !up1180Again.c46 && !up1180Again.c93);

// 模拟 1.1.20 早期宿主（无 dshPurgeWshLiteral，且无 launchCwd）
const legacy1120Shell = legacy1180Shell
  .replace(
    "function dshPurgeWshLiteral(value) {\n" +
    "\treturn JSON.stringify(String(value == null ? \"\" : value)).replace(/[^\\u0000-\\u007e]/g, function (ch) {\n" +
    "\t\treturn \"\\\\u\" + (\"0000\" + ch.charCodeAt(0).toString(16)).slice(-4);\n" +
    "\t});\n" +
    "}\n",
    ""
  )
  .replaceAll("dshPurgeWshLiteral(", "JSON.stringify(")
  .replace("\t\tfor (var i = 0; i < body.length; i++) { if (body.charCodeAt(i) > 127) throw new Error(\"desktop update script is not ascii\"); }\n", "");
const up1120 = applyDesktopUpdateChain(legacy1120Shell);
check("#46 + #93 串联升级 1.1.20 宿主且产物与全新 #45 完全一致", up1120.c45 === false && up1120.c46 === true && up1120.c93 === true && up1120.text === freshOut.text);

console.log(failed === 0 ? "\nALL PASS" : `\n${failed} FAILED`);
process.exit(failed === 0 ? 0 : 1);
