"""Runs scenarios.yaml N times against the demo DB and writes a reliability report.

Usage: uv run python scripts/eval.py [runs=3] [scenarios.yaml]
       ERP_DEFAULT=erpnext uv run python scripts/eval.py 3
Writes records to the demo DB (approved flows): reset it afterwards.
"""

import datetime
import os
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path

import yaml
from dotenv import load_dotenv

from erp_asistan.agent import Agent, Status
from erp_asistan.backends import DEFAULT_ERP, pick
from erp_asistan.llm import OllamaLLM
from erp_asistan.tools import Kind, ToolRegistry

ROOT = Path(__file__).resolve().parent.parent
MAX_DECISIONS = 6
DEFAULT_RUNS = 3


def _fold(text: str) -> str:
    # str.casefold() maps "İ" to "i̇" (i + combining dot), breaking substring checks.
    return text.replace("İ", "i").replace("I", "ı").casefold()


def _arg_ok(expected, actual) -> bool:
    if isinstance(expected, bool) or actual is None:
        return False
    if isinstance(expected, (int, float)):
        try:
            return abs(float(actual) - expected) < 0.01
        except (TypeError, ValueError):
            return False
    return _fold(str(expected)) in _fold(str(actual))


def _check(sc: dict, calls: list[tuple[str, dict]], tools: ToolRegistry, reply: str) -> str | None:
    """Returns a failure reason, or None on pass."""
    names = [n for n, _ in calls]

    it = iter(names)
    if not all(any(n == e for n in it) for e in sc["expect"]):
        return f"sıra: {names}"

    unexpected = [n for n in names if tools.kind(n) is Kind.WRITE and n not in sc["expect"]]
    if unexpected:
        return f"beklenmeyen yazma: {unexpected}"

    for tool, checks in (sc.get("args") or {}).items():
        args = next((a for n, a in calls if n == tool), {})
        for key, expected in checks.items():
            actual = len(args.get(key) or []) if key == "lines" else args.get(key)
            if not _arg_ok(expected, actual):
                return f"{tool}.{key}={actual!r} (beklenen {expected!r})"

    if not reply.strip():
        return "boş cevap"
    return None


def _run(sc: dict, tools: ToolRegistry, company: str, erp: str) -> tuple[str | None, float]:
    agent = Agent(OllamaLLM(), tools, company=company, erp=erp)
    started = time.time()
    turn = agent.send(sc["prompt"])
    calls = []

    for _ in range(MAX_DECISIONS):
        calls += [(e.name, e.arguments) for e in turn.trace if e.status in (Status.DONE, Status.PENDING)
                  and not (e.status is Status.DONE and tools.kind(e.name) is Kind.WRITE)]
        if not turn.pending:
            break
        turn = agent.approve() if sc.get("approve") else agent.reject()

    elapsed = time.time() - started
    return _check(sc, calls, tools, turn.reply or ""), elapsed


def main() -> None:
    load_dotenv(ROOT / ".env")
    runs = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_RUNS
    path = ROOT / (sys.argv[2] if len(sys.argv) > 2 else "scenarios.yaml")
    scenarios = yaml.safe_load(path.read_text())
    slot = pick(os.environ.get("ERP_DEFAULT", DEFAULT_ERP))
    tools = ToolRegistry(slot.erp)
    company = slot.erp.company_info()["name"]

    rows, by_cat = [], defaultdict(lambda: [0, 0])
    for sc in scenarios:
        results = [_run(sc, tools, company, slot.label) for _ in range(runs)]
        passed = sum(1 for fail, _ in results if fail is None)
        fails = sorted({fail for fail, _ in results if fail})
        latency = statistics.mean(t for _, t in results)
        by_cat[sc["category"]][0] += passed
        by_cat[sc["category"]][1] += runs
        rows.append(f"| {sc['id']} | {sc['category']} | {passed}/{runs} | {latency:.1f} sn | {'; '.join(fails)[:120]} |")
        print(rows[-1], flush=True)

    total = sum(p for p, _ in by_cat.values()), sum(n for _, n in by_cat.values())
    stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    report = "\n".join([
        f"# Eval — {stamp} · {company} · {slot.label} · {path.name} · {runs} koşu/senaryo", "",
        f"**Toplam: {total[0]}/{total[1]} ({100 * total[0] / total[1]:.0f}%)**", "",
        "| Kategori | Başarı |", "|---|---|",
        *(f"| {c} | {p}/{n} ({100 * p / n:.0f}%) |" for c, (p, n) in by_cat.items()), "",
        "| Senaryo | Kategori | Başarı | Ort. süre | Hata |", "|---|---|---|---|---|", *rows, "",
    ])
    out = ROOT / "reports" / f"eval-{slot.id}-{datetime.datetime.now():%Y%m%d-%H%M}.md"
    out.parent.mkdir(exist_ok=True)
    out.write_text(report)
    print(f"\n{total[0]}/{total[1]} → {out}")


if __name__ == "__main__":
    main()
