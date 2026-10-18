加载 `paper-autopilot` 技能并按其规范执行论文任务（SCI / 中文学位，同一套 22 步引擎）。

要求：
1. 先读本技能 `SKILL.md`，再只读当前步骤需要的那份 `references/`（不要一次全读）。
   已有项目时，同时读项目里的 `PIPELINE.md`、`PAPER_STATE.json`、`DECISIONS.md`。
2. 判模式：毕业论文/学位论文/开题 → CN 模式（先 `scaffold.py` 建骨架）；
   SCI/期刊/英文 → SCI 模式；已有项目/说"继续" → 续跑，只核对当前步产出是否真存在。
3. 主循环只用三条命令：`autopilot.py start` → `next`（读工单）→ `done`（过闸前进）。
   工单是唯一权威指令；确实做不了用 `skip --reason` 留痕，不要停、不要跳、不要瞒。
4. 五条铁律照办：不编数据、不编文献；每步过闸；不停下来提问（自选 + 记 `DECISIONS.md`）；
   去 AI 终检（19）在总检（20）之前；降级必须写进交付说明。
5. 交付前必须跑 `final_check.py --dir <项目> --write` 与 `selfcheck.py --dir <项目>`，
   **不通过不许交付**，未通过项与原因如实告诉用户。
6. 跑之前先确认解释器：需要 `requests` / `matplotlib` / `python-docx` / `pymupdf`；
   本机已验证 `D:\py\Python311\python.exe`。DSH 内置 python 缺这几个包。

用户参数（可为空）：
$ARGUMENTS
