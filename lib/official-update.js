// 官方客户端升级后的补丁回写标记。wscript 字面量给重启脚本用。
import path from "node:path";
import { hostFs as fs } from "./extract-asar.js";

const MARKER_NAME = "dsh-purge-reapply-asar";

function harnessExeName(exe) {
  const base = path.basename(String(exe || "")).toLowerCase();
  return base === "deepseek harness.exe" || base === "deepseek-harness.exe";
}

export function upgradeMarkerPath(exe) {
  if (!harnessExeName(exe)) return "";
  return path.join(path.dirname(exe), "resources", MARKER_NAME);
}

export function upgradeMarkerExists(exe) {
  const marker = upgradeMarkerPath(exe);
  return Boolean(marker && fs.existsSync(marker));
}

export function clearUpgradeMarker(exe) {
  const marker = upgradeMarkerPath(exe);
  if (!marker) return;
  try { fs.rmSync(marker, { force: true }); } catch { /* 下次启动再试 */ }
}

/**
 * 更新成功判定（纯函数，便于回归测试）。
 *
 * 不再拿 EXE / ASAR 的大小或时间戳当依据：官方安装器可能产出字节完全相同的文件，
 * 旧规则会因此判定“没更新” → 触发第二次安装 + 回滚 → 把一次成功更新变成事故。
 * 现在的依据只有两条：安装器退出码 == 0，以及必需资源（app.asar 或 app 目录）存在。
 * 大小变化只作为诊断字段返回。
 */
export function updateOutcomeOf(input = {}) {
  const exitCode = Number(input.exitCode);
  const resourcesOk = input.resourcesOk === true;
  const sizeChanged = input.exeSizeChanged === true || input.asarSizeChanged === true;
  if (!Number.isFinite(exitCode)) return { success: false, reason: "installer-exit-unknown", sizeChanged };
  if (exitCode !== 0) return { success: false, reason: `installer-exit-${exitCode}`, sizeChanged };
  if (!resourcesOk) return { success: false, reason: "resources-incomplete", sizeChanged };
  return { success: true, reason: sizeChanged ? "updated" : "updated-identical-bytes", sizeChanged };
}

/** 只认本次安装 resources 里由插件自己生成的隔离目录；真实 runtime / app / resources 根一律拒绝。 */
const STALE_DIR_RE = /^app\.dshpurge-(?:prev|failed)(?:-\d+)?$/;

export function isCleanableStaleDir(resourcesAbs, candidateAbs) {
  try {
    if (!resourcesAbs || !candidateAbs) return false;
    const res = path.resolve(String(resourcesAbs));
    const cand = path.resolve(String(candidateAbs));
    // 必须是 resources 的直接子项：dirname 相同，杜绝 ../.. 越界与嵌套路径。
    if (path.dirname(cand) !== res) return false;
    const name = path.basename(cand);
    if (!STALE_DIR_RE.test(name)) return false;
    const st = fs.lstatSync(cand);
    // 顶层是链接（junction / symlink）一律拒绝：绝不顺着链接去动真实目录。
    if (st.isSymbolicLink()) return false;
    if (!st.isDirectory()) return false;
    return true;
  } catch {
    return false;
  }
}

/**
 * 清理官方更新交接留下的隔离目录（app.dshpurge-prev* / app.dshpurge-failed-*）。
 *
 * 走 Node 的 fs.rmSync：对 app/runtime -> resources/runtime 这类 junction 只删链接本身，
 * 不会像 WSH 的 FSO.DeleteFolder 那样穿过链接删掉真实 runtime。
 * 每次删除前都用 isCleanableStaleDir 核对绝对路径与目录名；被拒绝的条目原样保留并记入报告。
 */
export function clearStaleExtractedApps(exe) {
  const report = { ok: true, removed: [], rejected: [], errors: [] };
  if (!harnessExeName(exe)) return report;
  const resources = path.join(path.dirname(exe), "resources");
  let names = [];
  try { names = fs.readdirSync(resources); } catch { return report; }
  for (const name of names) {
    if (!name.startsWith("app.dshpurge-")) continue;
    const full = path.join(resources, name);
    if (!isCleanableStaleDir(resources, full)) {
      // 名字不像隔离目录，或本身是顶层链接：不碰，留给人工确认。
      report.rejected.push(full);
      continue;
    }
    try {
      fs.rmSync(full, { recursive: true, force: true });
      report.removed.push(full);
    } catch (e) {
      report.ok = false;
      report.errors.push([full, String(e && e.message ? e.message : e)]);
    }
  }
  return report;
}

/** Windows Script Host 无 BOM 时按系统 ANSI 读文件。中文路径写成 \uXXXX，整份脚本保持 ASCII。 */
export function wshLiteral(value) {
  return JSON.stringify(String(value ?? "")).replace(/[\u007f-\uffff]/g, (ch) => {
    return "\\u" + ch.charCodeAt(0).toString(16).padStart(4, "0");
  });
}

export function isWshAscii(source) {
  const text = String(source || "");
  for (let i = 0; i < text.length; i += 1) {
    if (text.charCodeAt(i) > 0x7f) return false;
  }
  return true;
}
