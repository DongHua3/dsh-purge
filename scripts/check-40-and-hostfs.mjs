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

console.log(failed === 0 ? "\nALL PASS" : `\n${failed} FAILED`);
process.exit(failed === 0 ? 0 : 1);
