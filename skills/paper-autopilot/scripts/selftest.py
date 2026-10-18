#!/usr/bin/env python3
"""selftest — prove the pipeline works on this machine, without a human.

Builds a throwaway project in a temp directory, drives `autopilot.py` through
all 22 steps with minimal fixture content, then runs `selfcheck.py` and asserts
that the loop advanced every step and that the refusal mechanism actually
refuses.

    python selftest.py

Exit 0 = the install is functional. Exit 1 = something is broken.
Standard library only.
"""
from __future__ import annotations

import io
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
AUTO = os.path.join(HERE, "autopilot.py")
SELF = os.path.join(HERE, "selfcheck.py")


def _utf8() -> None:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except Exception:
            pass


def run(*args, expect=None):
    p = subprocess.run([sys.executable, *args], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if expect is not None and p.returncode != expect:
        print(f"!! exit {p.returncode} (expected {expect}) for {' '.join(args[1:4])}")
        print(p.stdout[-700:])
        print(p.stderr[-700:])
    return p


# Minimal structurally-valid content for every declared artifact. The text is
# deliberately bland: this test checks the plumbing, not the prose.
BIG = ("# Fixture\n\n" + ("This is filler content for the pipeline self test. " * 4)
       + "\n")

BODY = {
    "01_项目初始化/BRIEF.md":
        "# BRIEF\n\nvenue: Journal of Vibration and Control (SAGE, Q2)\n"
        "type: research article\nlength: 8000 words\nfigures: 10\n"
        "experiment: none (computational study)\n"
        "authors: 占位符（投稿前替换）\n",
    "02_检索式生成/SEARCH_STRINGS.md":
        "# Search strings\n\nbroad: (rotor OR shaft) AND vibration\n"
        "medium: (magnetorheological elastomer) AND absorber AND rotor\n"
        "narrow: \"magnetorheological elastomer\" AND \"dynamic vibration absorber\"\n",
    "03_检索与导出/SEARCH_LOG.md":
        "# Search log\n\nOpenAlex 2026-09-20 hits 412 exported 412\n"
        "Crossref 2026-09-20 hits 96 after dedup 61\n",
    "04_选题与空白识别/TOPIC.md":
        "# Topic\n\n1. Adaptive MRE absorber for rotor vibration.\n"
        "   gap: tuning is usually fixed\ng   risk: reluctance network, not a field solve\n",
    "05_对标库深度学习/BENCHMARK.md":
        "# Benchmarks\n\n1. A 2024 borrow the tolerance declaration\n"
        "2. B 2023 borrow the parameter table\n3. C 2022\n4. D 2021\n5. E 2020\n",
    "06_文献筛选分类/SELECTION.csv":
        "title,year,include,reason,class\nRotor vibration control,2024,Y,relevant,mechanism\n"
        "Unrelated work,2019,N,off topic,-\n",
    "07_导入引用库取全文/PDF_STATUS.md":
        "# PDF status\n\nhave 18, missing 3, list below\n",
    "08_文献精读/NOTES/n01.md":
        "# Note 01\n\n- key figure 62 percent reduction (p. 4, Table 2)\n- limit: single speed\n",
    "09_论文框架搭建/OUTLINE.md":
        "# Outline\n\n1 Introduction [Fig.1]\n2 Methods [Tab.1]\n"
        "3 Results [Fig.2]\n4 Discussion\n5 Conclusions\n",
    "10_图表制作与引用/FIGPLAN.md":
        "# Figure plan\n\nFig.1 architecture (own work)\nFig.2 material response (own work)\n"
        "Fig.3 sweep (own work)\nFig.4 verification (own work)\nFig.5 control (own work)\n",
    "manuscript/00_abstract.md":
        "# Abstract\n\nThe peak amplitude falls from 182.5485 um to 24.8135 um, a reduction "
        "of 86.4 percent. The controller uses more mean power than the best constant current.\n",
    "manuscript/01_intro.md":
        "# 1 Introduction\n\nRotor vibration limits the operating range of rotating "
        "machinery [1]. Passive absorbers cannot adapt to varying speed [2].\n",
    "manuscript/02_methods.md":
        "# 2 Methods\n\nThe shaft is a clamped-clamped beam of 350 mm span. The absorber is "
        "a 0.400 kg mass on a four-layer MRE pad. Mesh convergence used three grids of "
        "120000, 480000 and 1900000 elements.\n",
    "manuscript/03_results.md":
        "# 3 Results\n\nThe bare rotor peaks at 182.5485 um. The de-energized configuration "
        "reaches 101.9053 um. The best constant current gives 35.8675 um. The controller "
        "gives 24.8135 um.\n",
    "manuscript/04_discussion.md":
        "# 4 Discussion\n\nThe reduction is comparable to published adaptive absorbers [1]. "
        "The thermal result refutes the 1.0 A design current.\n",
    "manuscript/05_conclusions.md":
        "# 5 Conclusions\n\nAn adaptive MRE absorber with speed-scheduled current reduces "
        "the peak synchronous response. The result is a simulation prediction and has not "
        "been experimentally verified.\n",
    "manuscript/references.md":
        "# References\n\n[1] A. Rahman et al. (2024). Rotor vibration control. "
        "J. Sound Vib.\n[2] B. Li (2023). Tunable absorbers. Mech. Syst. Signal Process.\n",
    "14_目标期刊选择/JOURNALS.csv":
        "journal,issn,quartile,apc,risk\nJournal of Vibration and Control,1077-5463,Q2,"
        "subscription free to publish,low\n",
    "15_目标期刊格式学习/FORMAT_CHECKLIST.md":
        "# Format checklist\n\n- [x] abstract under 250 words\n- [x] 6 keywords\n"
        "- [x] numbered citations\n- [x] CRediT statement\n",
    "16_润色与语言打磨/scan_report.json":
        '{"all_pass": true, "failed": [], "gates": ['
        '{"key": "sent_cv", "value": 0.61, "pass": true}, '
        '{"key": "excess_vocab", "value": 0.0, "pass": true}, '
        '{"key": "conn_rate", "value": 0.4, "pass": true}], '
        '"note": "fixture written by selftest.py"}\n',
    "17_图片版权/RIGHTS.md":
        "# Rights\n\nAll figures generated by project scripts, no third-party rights.\n",
    "18_CoverLetter/Cover_Letter.md":
        "# Cover letter\n\nWe submit the enclosed manuscript. The peak amplitude is reduced "
        "by 86.4 percent. AI use is disclosed in the Acknowledgements.\n",
    "19_去AI痕迹/scan_after.json":
        '{"all_pass": true, "failed": [], "note": "fixture written by selftest.py"}\n',
    "19_去AI痕迹/statement.md":
        "# AI use statement\n\n**Use of generative AI.** The authors used an AI assistant "
        "for language editing and structuring. All scientific content and conclusions are "
        "the authors' own.\n",
    "19_去AI痕迹/diff_check.md":
        "# Edit comparison\n\n| before | after | number unchanged |\n|---|---|---|\n"
        "| peak falls to 24.8135 um | peak falls to 24.8135 um | yes |\n",
    "20_投稿前总检/PRESUBMIT_CHECK.md":
        "# Pre-submission check\n\n- [x] citations verified\n- [x] numbers traced\n"
        "- [x] figure numbers consecutive\n\n## Degraded steps\n\nnone\n",
    # step 20 requires the citation verification report; a real run produces it
    # with `litsearch.py verify`
    "refs/citation_verify.json":
        '{"refs_file": "manuscript/references.md", "verified_at": "fixture", '
        '"tally": {"VERIFIED": 2}, "blocking": 0, "results": ['
        '{"n": 1, "verdict": "VERIFIED", "problems": [], "fix": {}}, '
        '{"n": 2, "verdict": "VERIFIED", "problems": [], "fix": {}}]}\n',
    "21_返修/Response_Letter.md":
        "# Response to reviewers\n\nComment 1.1 addressed; see the revised Section 3.\n",
    "21_返修/CHANGES.md":
        "# Change log\n\n| comment | change | location |\n|---|---|---|\n",
    # shared directories have to be non-empty too.
    # NOTE: data/ is NOT written here. The self test generates it by actually
    # running the reference model, so the fixture exercises the provenance
    # chain instead of hand-writing numbers - which is the whole point.
    "refs/export.ris": "TY  - JOUR\nTI  - Rotor vibration control\nPY  - 2024\nER  -\n",
    "12_方法与结果/model_verify.json":
        '{"model": "rotor_mre_dva", "version": "1.0.0", "passed": true, '
        '"n_checks": 7, "n_passed": 7, "checks": [], '
        '"note": "produced by simulate.py check during the self test"}\n',
    "figures/fig01_architecture.pdf": "%PDF-1.4 fixture for the pipeline self test\n",
    "figures/fig02_material.pdf": "%PDF-1.4 fixture for the pipeline self test\n",
    "figures/fig03_sweep.pdf": "%PDF-1.4 fixture for the pipeline self test\n",
    "figures/fig04_verification.pdf": "%PDF-1.4 fixture for the pipeline self test\n",
    "figures/fig05_control.pdf": "%PDF-1.4 fixture for the pipeline self test\n",
    "submission/README.md":
        "# Submission package\n\nProduced by the paper-pipeline self test. "
        "Degraded steps: none.\n",
}


def write(root: str, rel: str, body: str) -> None:
    p = os.path.join(root, rel.replace("/", os.sep))
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with io.open(p, "w", encoding="utf-8") as fh:
        fh.write(body)


def main() -> int:
    _utf8()
    root = os.path.join(tempfile.gettempdir(), "paper_pipeline_selftest")
    shutil.rmtree(root, ignore_errors=True)
    failures: list[str] = []

    print("paper-pipeline self test\n")
    print(f"work dir: {root}\n")

    # --- 0. the step table must be sane ---------------------------------
    # A duplicate step id makes IDS.index() return the first occurrence, so the
    # pipeline loops on one step forever instead of failing loudly.
    sys.path.insert(0, HERE)
    try:
        import autopilot as A
        st_problems = A._check_step_table()
    except Exception as e:  # noqa: BLE001
        st_problems = [f"import autopilot failed: {type(e).__name__}: {e}"]
    if st_problems:
        print("  [!!] step table is broken:")
        for x in st_problems:
            print(f"       {x}")
        failures.extend(st_problems)
    else:
        print(f"  [ok] step table sane: {len(A.S)} steps, ids "
              f"{A.IDS[0]}..{A.IDS[-1]}, no duplicates")

    # --- 1. start -------------------------------------------------------
    p = run(AUTO, "start", "--dir", root,
            "--direction", "adaptive magnetorheological elastomer vibration "
                           "absorber with ANFIS control for rotor vibration",
            expect=0)
    if p.returncode != 0:
        return 1
    for line in p.stdout.splitlines():
        if line.startswith("[ok]"):
            print("  " + line)
    print()

    # --- 2. generate real data through the simulation chain -------------
    # data/ must be produced by an actual run, not written by hand, so the test
    # exercises simulate.py and the provenance sidecars it emits.
    SIM = os.path.join(HERE, "simulate.py")
    data_dir = os.path.join(root, "data")
    os.makedirs(data_dir, exist_ok=True)
    produced = []
    if os.path.isfile(SIM):
        for study, name in (("material_law", "material_law"),
                            ("speed_sweep", "speed_sweep"),
                            ("monte_carlo", "monte_carlo")):
            args = [sys.executable, SIM, "run", "--model", "rotor_mre_dva",
                    "--study", study, "--out", os.path.join(data_dir,
                                                            f"{name}.csv")]
            if study == "monte_carlo":
                args += ["--seed", "0", "--n", "60"]
            p = subprocess.run(args, capture_output=True, text=True,
                               encoding="utf-8", errors="replace")
            if p.returncode == 0:
                produced.append(f"{name}.csv")
            else:
                failures.append(f"simulate.py run {study} failed: "
                                f"{p.stderr.strip()[:200]}")
        if produced:
            print(f"  [ok] simulation produced real data: {', '.join(produced)}")
            p = subprocess.run([sys.executable, SIM, "provenance",
                                "--data", data_dir], capture_output=True,
                               text=True, encoding="utf-8", errors="replace")
            if p.returncode == 0:
                print("  [ok] data provenance verified")
            else:
                failures.append("provenance check failed on freshly "
                                "generated data")
        else:
            failures.append("no data was produced by the simulation chain")
    else:
        failures.append(f"simulate.py not found at {SIM}")

    # --- 3. the refusal mechanism must actually refuse ------------------
    p = run(AUTO, "done", "--dir", root, expect=1)
    if p.returncode != 1:
        failures.append("done did not refuse to advance on a missing artifact")
    else:
        print("  [ok] refuses to advance when the artifact is missing")

    write(root, "01_项目初始化/BRIEF.md", "x\n")
    p = run(AUTO, "done", "--dir", root, expect=1)
    if p.returncode != 1:
        failures.append("done did not refuse an empty stub artifact")
    else:
        print("  [ok] refuses to advance on a stub artifact")

    # --- 3. drive every step -------------------------------------------
    advanced = 0
    for _ in range(40):
        p = run(AUTO, "next", "--dir", root)
        if "全部步骤已完成" in p.stdout:
            break
        step = None
        for line in p.stdout.splitlines():
            if line.startswith("工单 · 第 "):
                step = line.split("第 ")[1].split(" 步")[0].strip()
                break
        if step is None:
            failures.append("could not parse the work order from `next`")
            break
        for rel, body in BODY.items():
            write(root, rel, body)
        p = run(AUTO, "done", "--dir", root)
        if p.returncode != 0:
            failures.append(f"step {step} could not be completed")
            break
        advanced += 1

    # `start` pre-completes step 00, so the loop drives the remaining 21.
    print(f"  [ok] advanced {advanced}/21 steps with no human input"
          if advanced == 21 else f"  [!!] advanced only {advanced}/21 steps")
    if advanced != 21:
        failures.append(f"only {advanced}/21 steps advanced")

    # --- 4. check + selfcheck ------------------------------------------
    p = run(AUTO, "check", "--dir", root)
    if "[缺件]" in p.stdout or "[降级]" in p.stdout:
        failures.append("autopilot check reports missing or degraded steps")
    else:
        print("  [ok] every completed step still has its artifacts")

    p = run(SELF, "--dir", root)
    if p.returncode == 0:
        print("  [ok] selfcheck found no blocking problem")
    else:
        for line in p.stdout.splitlines():
            if line.startswith("- "):
                print("       " + line[:150])
        failures.append("selfcheck reported blocking problems on a clean fixture")

    # --- 5. degradation must be recorded and disclosed ------------------
    d2 = os.path.join(tempfile.gettempdir(), "paper_pipeline_selftest_skip")
    shutil.rmtree(d2, ignore_errors=True)
    run(AUTO, "start", "--dir", d2, "--direction", "test direction for skip")
    run(AUTO, "skip", "--dir", d2, "--step", "01", "--reason", "selftest")
    st = os.path.join(d2, "PAPER_STATE.json")
    with io.open(st, encoding="utf-8") as fh:
        blob = fh.read()
    if '"degraded"' in blob and "selftest" in blob:
        print("  [ok] degradation is recorded in the state file")
    else:
        failures.append("skip did not record the degradation")
    shutil.rmtree(d2, ignore_errors=True)

    print()
    if failures:
        print("FAILED:")
        for x in failures:
            print(f"  - {x}")
        return 1
    print("PASS — the pipeline runs end to end on this machine.")
    print(f"     (the throwaway project is at {root})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
