# 打包、迁移与换机自检

这份文件回答一件事：**把这个技能搬到另一台机器、另一个 AI 客户端之后，怎么确认它还能跑。**
技能本身是纯文件（`.md` + `.py` + 数据模板），没有安装程序、没有后台服务、不写注册表；
迁移等于拷目录，风险全在依赖和路径上。

---

## 一、包里有什么，哪些必须一起走

```
paper-autopilot/
├── SKILL.md                 技能入口（Lead 维护，不要手改）
├── references/              13 份作业指导（22 步、去 AI、文献核验、中文学位论文口径…）
├── scripts/                 16 个可直接执行的脚本
├── models/                  2 个可跑通的仿真模型示例
└── assets/                  项目脚手架模板 + 一个真实案例包
```

**整个目录一起拷。** 不要只拷 `SKILL.md`——它里面的每一条指路都指向
`references/` 或 `scripts/` 下的具体文件，缺一个就是死链。

**不要拷进去的**：`__pycache__/`、`*.pyc`、临时日志、任何 `data/*.prov.json`
之外的运行残留。字节码和 Python 版本绑定，换机后是纯噪声。

---

## 二、各客户端的落点

| 客户端 | 落点 | 说明 |
|---|---|---|
| DSH（本机） | `%USERPROFILE%\.dsh\skills\paper-autopilot\` | 文件监视器会自动刷新，不必重启 |
| Claude Code | `%USERPROFILE%\.claude\skills\paper-autopilot\` | 同一套目录约定 |
| 其他支持 `skills/` 约定的客户端 | `<客户端目录>/skills/paper-autopilot/` | 认 `SKILL.md` 即可 |
| 只支持项目级规则 | `<项目>/.agents/skills/…` 或该客户端指定位置 | 注意别和项目自己的 `.dsh/` 混 |

**不要装到这些地方**：

- `…/skills/` **根目录下平铺**（把 `references/`、`scripts/` 直接倒进 skills 根）。
  本机 skills 根已经有同名的 `references/`、`scripts/`、`tests/`、`config/` 目录，
  平铺会互相覆盖，而且不会形成"一个技能"。
- `Desktop\打包\dist\`、`bundle\`、`tools\`：这些是构建产物与打包工具，重打包会被覆盖。
- `Program Files\` 之类需要管理员权限的目录：脚本要写 `__pycache__` 和输出文件。
- **OneDrive / 坚果云等同步目录**：Word 与同步进程抢文件锁，`build_docx.py` 会随机
  `PermissionError`。本机真实项目的技能放在 `C:\Users\ASUS\.dsh\skills\`（非同步盘），
  项目产物放在 `C:\Users\ASUS\Desktop\` 下。
- 已有的 `paper-pipeline\` 或 `thesis-pipeline\` **目录内部**：那是两个独立技能，
  把新包塞进去会破坏它们的相对路径（它们互相引用的是 `~/.dsh/skills/paper-pipeline/scripts/`）。

---

## 三、依赖：谁必须要什么

| 能力 | 依赖 | 缺失时的表现 | 补法 |
|---|---|---|---|
| 流程驱动、闸门、状态 | 仅标准库 | — | 无 |
| 字数统计、图号连续性 | 仅标准库 | — | 无 |
| AI 腔扫描 `prose_scan.py` | 仅标准库 | — | 无 |
| 文献检索核验 `litsearch.py` | `requests` | 启动即报 `litsearch needs requests` 并退出 | `pip install requests` |
| 出图 `figure_kit.py` | `matplotlib` + `numpy` + `pandas` | 顶层 `import matplotlib` 直接 ImportError | `pip install matplotlib pandas numpy` |
| 仿真 `simulate.py` | `numpy` | 自检项降级，跑数据失败 | `pip install numpy` |
| Word 生成 `build_docx.py` | `python-docx` | ImportError | `pip install python-docx` |
| docx→pdf `docx_to_pdf.py` | 本机 Word 或 WPS（COM） | COM 调用失败 | 装 Office/WPS；或手动另存 PDF |
| PDF 校验（页数/嵌图） | `pymupdf` | `final_check.py` 跳过这两项并注明 | `pip install pymupdf` |

**本机实测（捆绑解释器 `…\dsh-primary-runtime\dependencies\python\python.exe`）**：

```
python-docx ✓   pandas ✓   numpy ✓   Pillow ✓   openpyxl ✓
matplotlib ✗    requests ✗   win32com ✗
```

→ 用这个解释器可以跑 `autopilot.py`、`build_docx.py`、`build_refs.py`、
`check_refs.py`、`wordcount.py`、`prose_scan.py`、`final_check.py`（PDF 项跳过）；
**跑不了** `figure_kit.py`、`litsearch.py`、`docx_to_pdf.py`。
真实论文项目用的是完整发行版 `D:\py\Python311\python.exe`（装了 matplotlib / requests /
pywin32），这也是它当初能出 12 图、51 页 PDF 的原因。

**缺依赖但暂时不想装**：照样能启动项目、写 BRIEF、过闸门、算字数、扫 AI 腔；
把出图与检索挪到有依赖的机器上做，`data/` 与 `figures/` 是纯文件，随项目目录一起搬即可。

---

## 四、换机自检（四步，按顺序）

```powershell
$SK = "$env:USERPROFILE\.dsh\skills\paper-autopilot"
$PY = "D:\py\Python311\python.exe"      # 换成目标机的真实解释器

# 1) 全量语法检查：期望没有任何输出（0 错误）
& $PY -m py_compile (Get-ChildItem "$SK\scripts\*.py","$SK\models\*.py").FullName

# 2) 入口冒烟：三个 --help 都应退出码 0
& $PY "$SK\scripts\autopilot.py" --help
& $PY "$SK\scripts\build_docx.py" --help
& $PY "$SK\scripts\build_refs.py" --help

# 3) 环境探测：打印本机可用工具与技能目录
& $PY "$SK\scripts\check_env.py"

# 4) 端到端无人值守自测：最后一行必须是 PASS
& $PY "$SK\scripts\selftest.py"
```

`selftest.py` 会建临时项目、真跑一次仿真产生带溯源的数据、无人值守走完全部步骤、
验证"缺文件会被拒绝前进"、再跑内容自检。**看到 PASS 再开工**，看不到就按它打印的
失败项修依赖，不要跳过。

---

## 五、Windows 路径与编码的坑（都是踩过的）

1. **`python` 可能不是你要的那个。** Windows 自带的 `python.exe` 是 Microsoft Store 的
   跳转桩，`python -c` 能过、`python -m py_compile` 也会过，但 `pip install` 装到别处。
   一律用**绝对路径解释器**，并在文档里写清是哪一个。
2. **中文路径与空格**：脚本内部用 `pathlib`，没问题；但在 PowerShell 里必须加引号，
   并且不要用 `cd` 之后靠相对路径——每台机器的当前目录都不一样。
3. **控制台编码**：PowerShell 5.1 默认 GBK，直接 `>` 重定向会把中文写成乱码。
   脚本已在入口做 `sys.stdout.reconfigure(encoding="utf-8")`；重定向时再设
   `$env:PYTHONIOENCODING = "utf-8"` 更稳。
4. **写文件一律 UTF-8**：`.md` 用 UTF-8（带不带 BOM 都能被构建脚本读），
   `.py` 保留文件头 `# -*- coding: utf-8 -*-`。混用 GBK 会让 `prose_scan.py`
   的中文统计静默算成 0。
5. **长路径**：项目名一长，`deliverables/<中文题目>.docx` 很容易越过 260 字符。
   路径用短名，或开 `LongPathsEnabled`，或用 `\\?\` 前缀。
6. **文件占用**：`docx_to_pdf.py` 转 PDF 前确认 Word 没打开那个文件，否则 COM 抛异常。
   脚本会重试并提示，但根治办法是关掉 Word。
7. **换行符**：项目用 git 时设 `core.autocrlf=false`，否则整文件 diff，
   看不出版本差异，回滚时容易把内容改丢。
8. **拷贝后先清字节码**：删 `__pycache__`、`*.pyc`，否则可能加载到上一个 Python 版本的旧字节码，
   表现为"改了源码行为不变"（引擎教训库真实踩过）。

---

## 六、搬一个正在跑的项目

技能搬完，还要搬项目本身：

1. 整个项目目录拷走：`PIPELINE.md`、`PAPER_STATE.json`、`DECISIONS.md`、
   `00_…` 到 `21_…` 各阶段目录、`manuscript/`、`data/`、`figures/`、`deliverables/`。
2. `data/*.prov.json` 与 `MANIFEST*.json` **必须一起拷**——溯源核验靠它们，
   丢了 `selfcheck.py` 会把正常数据判成"来源不明"。
3. 在新机器上跑 `autopilot.py next --dir <项目>`，看它是否认得出当前步。
   认得出就接着跑；认不出说明 `PAPER_STATE.json` 没拷全或格式被改过。
4. `figures/` 与 `deliverables/` 里的历史产物**不要手工编辑**，
   要改就改 `manuscript/` 或 `code/`，然后重跑构建。

---

## 七、更新与回滚

- 更新：保留一份原包副本（`paper-autopilot.bak-<日期>/`），再整目录覆盖。
  只覆盖 `scripts/`、`references/`、`assets/` 不会动到项目数据。
- 回滚：把副本拷回原位，删 `__pycache__`，重跑第四节四步自检。
- **不要改动正在跑的项目里的 `PIPELINE.md` 结构**：`autopilot.py` 会重写它；
  人写的内容只加在"日志"和"未达标项"这类段落里。
