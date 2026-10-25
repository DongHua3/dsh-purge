/**
 * macOS 换包后重签。
 *
 * 官方桌面包是签过名的；把 `Contents/Resources/app.asar` 挪走、换成解开的
 * `Contents/Resources/app` 之后，bundle 的 CodeResources 与磁盘不再一致，
 * Gatekeeper 会让应用直接打不开（"is damaged and can't be opened"）。
 *
 * 插件原本完全没有这一步（全仓无 codesign 调用），而 extract-asar / desktop
 * 也没有平台判断 —— 也就是说 mac 上一按「应用」就会毁掉那个 app。
 *
 * 这里做的是**临时签名**（`--sign -`，ad-hoc）：不需要开发者证书，能把 bundle
 * 重新封成自洽的，本机可以正常启动。它不能、也不打算替代官方签名。
 *
 * 平台语义：
 *   · darwin 以外的平台一律跳过（Windows/Linux 没有这套签名校验）。
 *   · darwin 上任何一步失败都**抛错**，由调用方回滚到换包前的状态 ——
 *     留一个签名失效的 app 比直接失败更糟。
 */
import { spawnSync } from "node:child_process";
import fs from "node:fs";

/** 从可执行文件往上找到 .app 包根；找不到返回空串。 */
export function appBundleOf(exe) {
  const raw = String(exe || "");
  if (!raw) return "";
  // 用原始串切，避免 path.normalize 在非 POSIX 平台吃掉前导分隔符
  const norm = raw.replace(/\\/g, "/");
  const marker = "/Contents/MacOS/";
  const at = norm.indexOf(marker);
  if (at <= 0) return "";
  const head = norm.slice(0, at);
  if (!head.endsWith(".app")) return "";
  return head;
}

function runCodesign(args) {
  const res = spawnSync("codesign", args, {
    encoding: "utf8",
    stdio: ["ignore", "pipe", "pipe"],
    timeout: 180000,
    windowsHide: true,
  });
  return {
    ok: res.status === 0,
    status: res.status,
    stdout: String(res.stdout || "").trim(),
    stderr: String(res.stderr || "").trim(),
    error: res.error ? String(res.error.message || res.error) : "",
  };
}

/**
 * 换包后重签 bundle。
 *
 * @param {string} exe 官方桌面可执行文件（…/X.app/Contents/MacOS/X）
 * @returns {{ skipped?: string, ok?: boolean, bundle?: string, argv?: string[], stderr?: string }}
 * @throws 在 darwin 上重签失败时抛出，调用方必须回滚
 */
export function resignBundleAfterSwap(exe) {
  if (process.platform !== "darwin") return { skipped: "not_darwin" };
  const bundle = appBundleOf(exe);
  if (!bundle) return { skipped: "no_bundle" };
  if (!fs.existsSync(bundle)) return { skipped: "bundle_missing" };

  // --force: 覆盖原签名（原签名已经因为资源变动失效）
  // --deep:  连 Contents/Frameworks 里的嵌套 bundle 一起签
  // --sign -: ad-hoc，无需证书
  const argv = ["--force", "--deep", "--sign", "-", bundle];
  const first = runCodesign(argv);
  if (first.ok) return { ok: true, bundle, argv };

  // --deep 在新版 macOS 上已被标记弃用，个别 Xcode 版本会直接拒绝。
  // 退一步只签外层 bundle：资源变动由外层 CodeResources 覆盖，通常够启动。
  const fallback = ["--force", "--sign", "-", bundle];
  const second = runCodesign(fallback);
  if (second.ok) return { ok: true, bundle, argv: fallback, fellBack: true };

  const detail = [first.stderr, first.error, second.stderr, second.error].filter(Boolean).join(" | ");
  throw new Error(`macOS 换包后重签失败（${bundle}）: ${detail || "codesign 无输出"}`);
}

/** 供状态展示：这个平台换包后需不需要重签。 */
export function needsResign() {
  return process.platform === "darwin";
}
