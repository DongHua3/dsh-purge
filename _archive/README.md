# dsh-purge 上游存档说明

本仓库是 **YuJunZhiXue/dsh-purge** 在原作者下架前的完整镜像，用于存档与研究。

- 原仓库：`https://github.com/YuJunZhiXue/dsh-purge`（**已于 2026-10-21 下架，现返回 404**）
- 原作者：**YuJunZhiXue**（小杨）
- 存档时间：2026-10-21
- 镜像来源：下架前用 `git clone --mirror` 完整克隆（含 `refs/pull/*`），并补入第三方存档

**一切权利与署名归原作者。** 本仓库不主张任何原创性，不做再授权，不用于任何收费行为。

---

## 一、仓库结构

| 引用 | 内容 |
|---|---|
| `master` | 上游 master 的**原始 HEAD**：`8df4406`（2026-10-19），未做任何改动 |
| `fix/restart-sticky` | 上游遗留的僵尸分支（领先 0、落后 130），原样保留 |
| `upstream-archive` | 第三方镜像 @mmparko 于 2026-10-13 抓取的 issue/PR 快照 |
| `archive/notes` | 本分支：issue 存档的可读版本 + 完整度分析报告 |
| 113 个标签 | 73 个上游原始标签（`v1.1.1` … `v1.1.71`、`restore-issue-25`）+ 39 个 `archive/pr-*`（37 个 PR 头 + 2 个 merge）+ 1 个快照标签 |

`archive/pr-*` 标签是把 GitHub 的 `refs/pull/*` 转成标签保存——GitHub 不允许向 `refs/pull/*` 推送，转标签是唯一能跨仓库保留 PR 内容的方式。

---

## 二、issue 存档完整度

| 编号区间 | 标题 | 正文 | 评论 | 来源 |
|---|---|---|---|---|
| #1 – #115 | ✅ | ✅ | ✅ | @mmparko 2026-10-13 抓取 |
| #116 – #125 | ❌ | ❌ | ❌ | 原仓库下架，永久缺失 |
| #126 – #150 | ✅ | ❌ | ❌ | 2026-10-20 API 查询的残留记录 |

文件清单：

| 文件 | 说明 |
|---|---|
| `ISSUES-DIGEST.md` | 人读版：91 个 issue + 24 个 PR 的标题、正文、全部评论 |
| `issues-and-prs.json` | API 原始响应（issues + PRs 全字段） |
| `issue-comments.json` | 按 issue 编号归类的评论 |
| `labels.json` | 仓库标签定义 |
| `repo-metadata.json` | 元数据快照（star / fork / topics / license） |
| `ISSUES-116-150-补录.md` | #126–#150 的标题级补录（无正文） |
| `dsh-purge-深度分析报告.md` | 对本仓库的完整分析：提交历史、分支标签、PR 生态、工程质量、合规机制、风险矩阵 |

---

## 三、已知缺口

1. **issue #116–#125**：连标题都没有。
2. **issue #126–#150 的正文与评论**：原仓库下架后无法获取；Wayback Machine 抓取时处于 503 维护，恢复后可尝试。
3. **GitHub Releases 的 zip 附件**：仓库下架后下载链接全部失效。源码可用 `git archive` 重新打包，但原始产物哈希无法复原。
4. **作者 Telegram 频道（t.me/LLM_PoJia/271）内的闭源版本**：从未公开，不在本存档范围。

---

## 四、许可说明

| 版本区间 | 许可 |
|---|---|
| `v1.1.1` – `v1.1.71`（tag 指向的提交） | MIT |
| `master` 末端（2026-10-19 起） | 作者改为**专有商业许可**，声明保留所有权利、禁止再分发 |

本仓库以存档为目的保留原始提交与原始 LICENSE 文件，**未对任何上游文件做修改**。如需商业使用、二次分发或白标，请按原作者要求取得授权（原作者联系邮箱见原 README）。

---

## 五、校验方式

`master`、`fix/restart-sticky` 与全部 `v*` 标签的 commit SHA 与上游完全一致，可逐项核对：

```bash
git ls-remote https://github.com/DongHua3/dsh-purge.git
git log -1 --format=%H master          # 应为 8df4406a7c5bddc01091ed20608417390cb457ee
git rev-parse v1.1.71                  # 应为 5e757260a0be055892b48ec520d451cc82e1c191
```

完整离线备份另有 `dsh-purge-full.bundle`（5.3 MB，`git bundle verify` 通过），可由存档持有者另行保管。
