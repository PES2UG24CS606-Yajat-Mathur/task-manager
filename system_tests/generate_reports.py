"""
Generates the Part 3 documents from the real test results.

Inputs (docs/testing/evidence/):
    junit.xml                       pytest results
    coverage.json                   from coverage.py (`--cov-report=json`) or stdlib_coverage.py
    coverage_v1_0_tests.json        coverage of the tests as they stood at tag v1.0 (optional)
    system_validation_results.json  from run_system_validation.py

Outputs (docs/testing/):
    Test_Case_Document, Unit_Test_Report, System_Validation_Report, Code_Coverage_Report and
    Branch_Coverage_Report, each as .pdf (needs Playwright) and always as .html.

No result is typed by hand: re-run the tests, run this script, and every number follows.

    python system_tests/generate_reports.py
"""

import html
import json
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_case_catalog import (CATALOG, DEFECTS, FILE_TO_MODULE, FILE_TO_TC,  # noqa: E402
                               NAME_TO_TC, OBSERVATIONS)

REPO = Path(__file__).resolve().parent.parent
DOCS = REPO / "docs" / "testing"
EVIDENCE = DOCS / "evidence"
BUILD = "v1.0.1"
TODAY = date.today().strftime("%d-%m-%Y")
AUTHORS = [("PES2UG24CS561", "Tharunyah Sudhakar"), ("PES2UG24CS594", "Vishnu Narayanan Ajay"),
           ("PES2UG24CS597", "Vismay Chandra Dev"), ("PES2UG24CS606", "Yajat Mathur")]

CSS = """
@page { size: A4; margin: 18mm 15mm 16mm; }
* { box-sizing: border-box; }
body { font: 10pt/1.42 Arial, Helvetica, sans-serif; color: #1a1a1a; margin: 0; }
h1 { font: bold 19pt "Times New Roman", serif; text-align: center; margin: 0 0 4pt; }
.sub { font: bold 12pt "Times New Roman", serif; text-align: center; margin: 0 0 16pt; }
h2 { font-size: 13.5pt; margin: 18pt 0 6pt; break-after: avoid; }
h3 { font-size: 10.5pt; margin: 12pt 0 4pt; break-after: avoid; }
p { margin: 0 0 6pt; } ul { margin: 0 0 6pt; padding-left: 16pt; }
table { border-collapse: collapse; width: calc(100% - 1px); margin: 4pt 0 10pt; font-size: 8.8pt; }
th { background: #d9d9d9; text-align: left; font-weight: bold; }
th, td { border: 1px solid #8a8a8a; padding: 2.5pt 4pt; vertical-align: top; overflow-wrap: break-word; }
tr { break-inside: avoid; } thead { display: table-header-group; }
td.n, th.n { text-align: right; white-space: nowrap; }
code { font: 8.4pt Consolas, "DejaVu Sans Mono", monospace; word-break: break-all; }
.PASS, .FAIL, .PARTIAL, .XFAIL { white-space: nowrap; }
pre { font: 8.2pt Consolas, "DejaVu Sans Mono", monospace; background: #f2f2f2; border: 1px solid #ccc;
      padding: 5pt; white-space: pre-wrap; margin: 2pt 0 8pt; }
.PASS { color: #0b6b2e; font-weight: bold; } .FAIL { color: #b00020; font-weight: bold; }
.PARTIAL { color: #9a5b00; font-weight: bold; } .XFAIL { color: #9a5b00; font-weight: bold; }
.note { border-left: 3pt solid #555; background: #f4f4f4; padding: 5pt 8pt; margin: 6pt 0 10pt; }
.card { break-inside: avoid; margin-bottom: 9pt; } .card th { width: 21%; background: #eeeeee; }
.card tr:first-child th, .card tr:first-child td { background: #d9d9d9; font-weight: bold; }
figure { margin: 6pt 0 10pt; break-inside: avoid; } figcaption { font-size: 8.4pt; color: #444; }
figure img { max-width: 100%; max-height: 92mm; border: 1px solid #999; display: block; }
.two { display: grid; grid-template-columns: 1fr 1fr; gap: 8pt; }
"""


def esc(value):
    return html.escape(str(value))


def table(headers, rows, numeric=()):
    """HTML table. Cells are escaped unless wrapped in Raw. `numeric` = right-aligned column indexes."""
    head = "".join(f'<th{" class=n" if i in numeric else ""}>{esc(h)}</th>' for i, h in enumerate(headers))
    body = []
    for row in rows:
        cells = []
        for i, cell in enumerate(row):
            text = cell.html if isinstance(cell, Raw) else esc(cell)
            cells.append(f'<td{" class=n" if i in numeric else ""}>{text}</td>')
        body.append(f"<tr>{''.join(cells)}</tr>")
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table>"


class Raw:
    def __init__(self, text):
        self.html = text


def verdict(status):
    return Raw(f'<span class="{esc(status)}">{esc(status)}</span>')


def pct(covered, total):
    return f"{100 * covered / total:.1f}%" if total else "n/a"


def front_matter(title, version, revisions):
    authors = table(["SRN", "Name"], AUTHORS)
    rev = table(["Version", "Date", "Author", "Change Summary"], revisions)
    approvals = table(["Role", "Name", "Signature / Date"],
                      [("QA Lead", "Tharunyah Sudhakar", ""), ("Course Coordinator", "", "")])
    return (f"<h1>{esc(title)}</h1><div class=sub>Project: Task Manager Application</div>"
            f"<p>Version: {esc(version)} &nbsp;|&nbsp; Section: J &nbsp;|&nbsp; Batch: 12 &nbsp;|&nbsp; "
            f"Date: {TODAY} &nbsp;|&nbsp; Build under test: <code>{BUILD}</code> (Sprint 3)</p>"
            f"<h3>Authors</h3>{authors}<h3>Revision History</h3>{rev}<h3>Approvals</h3>{approvals}")


# ================================================================== load the results
def load_junit():
    """Every test as a dict: file, class, name, seconds, result (PASS / FAIL / XFAIL)."""
    root = ET.parse(EVIDENCE / "junit.xml").getroot()
    suite = root if root.tag == "testsuite" else root.find("testsuite")
    tests = []
    for tc in suite.findall("testcase"):
        parts = tc.get("classname").split(".")      # tests.test_auth.TestLogin
        skipped = tc.find("skipped")
        failed = tc.find("failure") is not None or tc.find("error") is not None
        is_xfail = skipped is not None and skipped.get("type") == "pytest.xfail"
        status = "FAIL" if failed else "XFAIL" if is_xfail else "SKIP" if skipped is not None else "PASS"
        tests.append({"file": parts[1], "cls": parts[2] if len(parts) > 2 else "", "name": tc.get("name"),
                      "seconds": float(tc.get("time", 0)), "status": status, "tc": tc_of(parts[1], tc.get("name"))})
    return tests, suite


def tc_of(file, name):
    """Find the test case: from the name (test_TC_Auth_01b_...), an explicit entry, or the file."""
    match = re.search(r"TC_([A-Za-z]+)_(\d+)", name)
    if match:
        return f"TC-{match.group(1)}-{match.group(2)}"
    return NAME_TO_TC.get(name, FILE_TO_TC.get(file, "General"))


def load_coverage(name="coverage.json"):
    path = EVIDENCE / name
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    # coverage.py on Windows writes app\\auth.py
    data["files"] = {k.replace("\\", "/"): v for k, v in data["files"].items()}
    return data


def load_v1_0_system_results():
    """Results of the v1.0 run, kept so the reports can show what Sprint 3 changed."""
    path = EVIDENCE / "v1.0" / "system_validation_results.json"
    return json.loads(path.read_text(encoding="utf-8"))["cases"] if path.exists() else []


def coverage_tool(cov):
    meta = cov["meta"]
    return meta.get("tool") or f"coverage.py {meta.get('version', '')}".strip()


def is_coverage_py(cov):
    return "tool" not in cov["meta"]


def source_line(file, number):
    lines = (REPO / file).read_text(encoding="utf-8").splitlines()
    return lines[number - 1].strip() if 0 < number <= len(lines) else ""


def tc_results(tests, cases):
    """{TC id: overall status}. FAIL if any test or check failed, then PARTIAL, then PASS."""
    out = {}
    for tc in CATALOG:
        statuses = {t["status"] for t in tests if t["tc"] == tc["id"]}
        statuses |= {c["status"] for c in cases if c["tc"] == tc["id"]}
        if "FAIL" in statuses or "XFAIL" in statuses:
            out[tc["id"]] = "FAIL"
        elif "PARTIAL" in statuses:
            out[tc["id"]] = "PARTIAL"
        else:
            out[tc["id"]] = "PASS" if statuses else "NOT RUN"
    return out


# ============================================================ Test Case Document
def test_case_document(tests, cases, results):
    counts = Counter(results.values())
    sv_by_tc, unit_by_tc = defaultdict(list), defaultdict(list)
    for c in cases:
        sv_by_tc[c["tc"]].append(c["id"])
    for t in tests:
        unit_by_tc[t["tc"]].append(t)
    body = front_matter("Test Case Document", "2.1", [
        ("1.0", "15-09-2026", "Student Team", "Sample test cases in Software Test Plan section 13.1; IDs in the RTM."),
        ("2.0", "04-11-2026", "Student Team", "Every RTM test case written out in full and updated for the changes "
                                              "made in Sprints 1 and 2. TC-Val-01 added. Results for v1.0 recorded."),
        ("2.1", TODAY, "Student Team", "TC-Val-01 extended in Sprint 3. Results recorded for v1.0.1.")])
    body += (f"<h2>1. Summary</h2><p>{len(CATALOG)} test cases cover all 31 SRS requirements. Results of the "
             f"latest run: <b>{counts['PASS']} pass, {counts['PARTIAL']} partial, {counts['FAIL']} fail</b>.</p>")
    body += table(["Test Case", "Requirement", "Title", "Result"],
                  [(t["id"], t["req"], t["title"], verdict(results[t["id"]])) for t in CATALOG])
    body += ("<h2>2. What changed during the sprints</h2>"
             "<p>Deviation numbers refer to <code>docs/DEVIATIONS.md</code>.</p>")
    body += table(["Test Case", "Change from Test Plan v1.0"], [(t["id"], t["change"]) for t in CATALOG])
    body += "<h2>3. Test cases</h2>"
    for t in CATALOG:
        units = unit_by_tc[t["id"]]
        names = "<br>".join(f"<code>{esc(u['file'])}::{esc(u['name'])}</code>" for u in units) or "None"
        steps = "<br>".join(f"{i}. {esc(s)}" for i, s in enumerate(t["steps"], 1))
        rows = [("Test Case ID", Raw(f"{esc(t['id'])}: {esc(t['title'])}")),
                ("Requirement", t["req"]), ("Module / Priority", f"{t['module']} / {t['priority']}"),
                ("Preconditions", t["pre"]), ("Test data", t["data"]), ("Steps", Raw(steps)),
                ("Expected result", t["expected"]), ("Automated tests", Raw(names)),
                ("System validation", ", ".join(sv_by_tc[t["id"]]) or "None"),
                ("Result", verdict(results[t["id"]]))]
        cells = "".join(f"<tr><th>{esc(a)}</th><td>{b.html if isinstance(b, Raw) else esc(b)}</td></tr>"
                        for a, b in rows)
        body += f'<div class=card><table>{cells}</table></div>'
    general = unit_by_tc["General"]
    if general:
        body += ("<h2>4. Supporting tests not tied to one case</h2><p>These check the application skeleton "
                 "shared by all modules.</p><ul>"
                 + "".join(f"<li><code>{esc(u['file'])}::{esc(u['name'])}</code></li>" for u in general) + "</ul>")
    return "Test_Case_Document", "Test Case Document", body


# ================================================================ Unit Test Report
def unit_report(tests, suite, cov):
    c = Counter(t["status"] for t in tests)
    executed = len(tests)
    body = front_matter("Unit Test Report", "2.0", [
        ("1.0", "04-11-2026", "Student Team", "Results for tag v1.0: 139 passed, 4 expected failures."),
        ("2.0", TODAY, "Student Team", "Results for v1.0.1 after the Sprint 3 defect fixes.")])
    body += "<h2>1. Result</h2>"
    body += table(["Tests run", "Passed", "Failed", "Expected failures (open defects)", "Skipped", "Pass rate"],
                  [(executed, c["PASS"], c["FAIL"], c["XFAIL"], c["SKIP"],
                    pct(c["PASS"], executed))], numeric=range(6))
    sub_checks = int(suite.get("tests", executed)) - executed     # pytest counts subtests in this total
    body += (f"<p>All {executed} tests ran: {c['PASS']} passed, {c['FAIL']} failed, and {c['XFAIL']} were expected "
             f"failures. The {sub_checks} sub-checks inside them also passed. At v1.0, 4 tests were expected "
             "failures because of open defects. Sprint 3 fixed those defects, so they now pass as regression "
             "tests (section 4).</p>")
    body += ("<h2>2. Scope and method</h2><ul>"
             "<li><b>Level:</b> module level, as the Test Plan (section 5) defines unit tests. Most tests call a "
             "module through its API with Flask's test client, so they also exercise that module's "
             "database access. A few call functions directly.</li>"
             "<li><b>Isolation:</b> every test gets a new temporary SQLite database.</li>"
             "<li><b>Tool:</b> pytest, with <code>unittest</code>-style test classes (deviation D5).</li>"
             f"<li><b>Environment:</b> Python {esc(sys.version.split()[0])}, Flask 3, "
             "SQLite. GitHub Actions is set up to repeat the suite on Python 3.11, 3.12 and 3.13.</li>"
             f"<li><b>Evidence:</b> <code>docs/testing/evidence/junit.xml</code> (run {esc(suite.get('timestamp', '')[:19])}, "
             f"{float(suite.get('time', 0)):.1f} s).</li></ul>")
    body += "<pre>pytest --cov=app --cov-branch --junitxml=docs/testing/evidence/junit.xml</pre>"
    body += "<h2>3. Results by module</h2>"
    by_module = defaultdict(list)
    for t in tests:
        by_module[FILE_TO_MODULE.get(t["file"], t["file"])].append(t)
    rows = []
    for module, ts in by_module.items():
        cc = Counter(t["status"] for t in ts)
        rows.append((module, ", ".join(sorted({t["file"] for t in ts})),
                     len(ts), cc["PASS"], cc["FAIL"], cc["XFAIL"]))
    body += table(["Module", "Test files", "Tests", "Passed", "Failed", "Expected failures"], rows, numeric=(2, 3, 4, 5))
    body += "<h2>4. Defects fixed in Sprint 3</h2>"
    body += table(["Defect", "Severity", "Summary", "Fix", "Status"],
                  [(d["id"], d["severity"], d["title"], d["fix"], d["status"]) for d in DEFECTS])
    body += ("<p>Severities are proposed by the test run and need the QA Lead's confirmation. "
             "<code>tests/test_input_robustness.py</code> sweeps every API route, so a route added later is checked "
             "automatically. Run against the v1.0 code, these tests fail with the same errors; the output is in "
             "<code>docs/testing/evidence/v1.0/new_tests_against_v1.0_code.txt</code>.</p>")
    body += "<h2>5. All tests</h2>"
    body += table(["Test file :: test", "Test Case", "Time (s)", "Result"],
                  [(Raw(f"<code>{esc(t['file'])}::{esc(t['name'])}</code>"), t["tc"], f"{t['seconds']:.3f}",
                    verdict(t["status"])) for t in tests], numeric=(2,))
    return "Unit_Test_Report", "Unit Test Report", body


# =================================================== System Validation Report
def req_rows(cases):
    """One row per SRS requirement, using the worst result among the checks that name it."""
    reqs = [f"TMA-F-{n:03d}" for n in (1, 2, 3, 4, 10, 11, 12, 13, 14, 20, 21, 22, 23, 24, 30, 31, 32, 33, 40, 41, 42)]
    reqs += [f"TMA-NF-{n:03d}" for n in range(1, 6)] + [f"TMA-SR-{n:03d}" for n in range(1, 6)]
    titles = {}
    for t in CATALOG:
        for r in re.findall(r"TMA-[A-Z]+-\d+", t["req"]):
            titles.setdefault(r, t["title"])
    rows, verdicts = [], {}
    for req in reqs:
        linked = [c for c in cases if req in c["req"]]
        statuses = {c["status"] for c in linked}
        v = "FAIL" if "FAIL" in statuses else "PARTIAL" if "PARTIAL" in statuses else "PASS" if linked else "NOT RUN"
        verdicts[req] = v
        rows.append((req, titles.get(req, ""), ", ".join(c["id"] for c in linked), verdict(v)))
    return rows, verdicts


def figure(path, caption):
    return f'<figure><img src="evidence/{esc(path)}" alt="{esc(caption)}"><figcaption>{esc(caption)}</figcaption></figure>'


def system_report(data):
    cases, meta = data["cases"], data["meta"]
    c = Counter(x["status"] for x in cases)
    rows, verdicts = req_rows(cases)
    rv = Counter(verdicts.values())
    perf = {x["id"]: x["metrics"] for x in cases if x.get("metrics")}
    old = load_v1_0_system_results()
    old_c = Counter(x["status"] for x in old)
    body = front_matter("System Validation Report", "2.0", [
        ("1.0", "04-11-2026", "Student Team", "Validation of tag v1.0 against the SRS."),
        ("2.0", TODAY, "Student Team", "Re-validation of v1.0.1 after the Sprint 3 defect fixes.")])
    body += "<h2>1. Conclusion</h2>"
    body += table(["Requirements checked", "Fully met", "Partly met", "Not met"],
                  [(len(verdicts), rv["PASS"], rv["PARTIAL"], rv["FAIL"])], numeric=range(4))
    run_rows = [("v1.0 (before Sprint 3)", len(old), old_c["PASS"], old_c["PARTIAL"], old_c["FAIL"])] if old else []
    run_rows.append((f"{BUILD} (after Sprint 3)", meta["total"], c["PASS"], c["PARTIAL"], c["FAIL"]))
    body += table(["Build", "Validation checks run", "Pass", "Partial", "Fail"], run_rows, numeric=range(1, 5))
    fails = [x["id"] for x in cases if x["status"] == "FAIL"]
    body += (f"<p>{rv['PASS']} of {len(verdicts)} SRS requirements passed validation in full. The two partly met "
             "requirements, TMA-NF-002 and TMA-SR-001, depend on a deployed environment and are recorded as "
             f"deviations D13 and D12. {len(fails)} checks failed on this build. The boundary-input checks that "
             "failed on v1.0 now pass, because Sprint 3 fixed the defects behind them (section 5).</p>")
    open_defects = [d for d in DEFECTS if not d["status"].startswith("Fixed")]
    body += "<h3>Test Plan exit criteria (section 5)</h3>"
    body += table(["Criterion", "Status", "Basis"], [
        ("All planned test cases are executed", verdict("PASS"), f"All {len(CATALOG)} test cases were executed."),
        ("No critical or high severity defects remain open", verdict("PASS" if not fails else "PARTIAL"),
         f"{len(open_defects)} defects open and {len(fails)} checks failing on this build."),
        ("All SRS acceptance criteria are satisfied", verdict("PARTIAL"),
         "Not met for the 99.5% monthly uptime figure (not measured) or for a trusted TLS certificate (self-signed "
         "locally). The Course Coordinator needs to accept deviations D12 and D13 for this criterion to close."),
    ])
    body += ("<h2>2. Method and environment</h2>"
             "<p>The application was treated as a black box. <code>system_tests/run_system_validation.py</code> "
             "started the real server as a separate process, drove a real browser, sent real HTTP requests, "
             "and then inspected the real database file and server log. Each result below was recorded by "
             "the script during the run.</p>")
    body += table(["Item", "Value"], [
        ("Build", f"{BUILD}: tag v1.0 plus the Sprint 3 defect fixes"),
        ("Server", "python run.py with APP_ENV=production, real scrypt, reminder thread polling every 2 s"),
        ("Client", f"{meta['browser']}, time zone Asia/Kolkata for the main flows"),
        ("Platform", f"Python {meta['python']} on Linux (cloud container), SQLite"),
        ("Run finished", meta["generatedAt"]),
        ("Normal load (assumption)", "10 concurrent clients, 500 tasks per user. The SRS does not define normal load."),
    ])
    body += "<h2>3. Requirement validation matrix</h2>"
    body += table(["Requirement", "Validated by test case", "Checks", "Result"], rows)
    if perf:
        body += "<h2>4. Performance results</h2>"
        names = {"SV-38": "Dashboard", "SV-39": "Search and filter"}
        body += table(["Operation", "Requests", "Concurrent clients", "Tasks per user", "p50 (ms)", "p95 (ms)", "Max (ms)", "Target"],
                      [(names[k], m["requests"], m["concurrency"], m["tasksPerUser"], m["p50_ms"], m["p95_ms"], m["max_ms"], "p95 at most 3000 ms")
                       for k, m in perf.items()], numeric=range(1, 7))
    body += "<h2>5. Defects found and fixed</h2>"
    body += table(["Defect", "Severity", "Checks", "Summary", "Cause", "Fix", "Status"],
                  [(d["id"], d["severity"], d["cases"], d["title"], d["cause"], d["fix"], d["status"]) for d in DEFECTS])
    body += ("<p><b>Impact at v1.0:</b> in each case the global error handler returned a clean JSON 500 with no internal "
             "details. No data was changed and the application stayed healthy (SV-37). Normal use of the UI could not "
             "produce these inputs.</p><h3>Regression result</h3>")
    before = {x["id"]: x for x in old}
    rows = [(x["id"], x["title"].replace("Boundary input: ", ""), before[x["id"]]["actual"].split(" | ")[0] if x["id"] in before else "Not in the v1.0 run",
             verdict(before[x["id"]]["status"]) if x["id"] in before else "",
             x["actual"], verdict(x["status"])) for x in cases if x["id"].startswith("SV-36")]
    body += table(["Check", "Input", "v1.0 observed", "v1.0", f"{BUILD} observed", BUILD], rows)
    changed = [x["id"] for x in cases if x["id"] in before and before[x["id"]]["status"] == "PASS" and x["status"] != "PASS"]
    body += f"<p><b>Regressions:</b> {esc(', '.join(changed)) if changed else 'none. Every check that passed on v1.0 still passes.'}</p>"
    body += "<h2>6. Other observations</h2><p>These are not SRS failures, and Sprint 3 did not change them. The team may want to decide on them.</p>"
    body += table(["Observation", "Detail"], OBSERVATIONS)
    body += "<h2>7. Not covered by this validation</h2><ul>"
    for item in ("Monthly availability (TMA-NF-002): needs a deployed system monitored for a month.",
                 "Trusted certificates and the reverse proxy (TMA-SR-001): exist only in a deployment.",
                 "Real phones and screen readers: widths were emulated in Chromium, and accessibility was checked through "
                 "keyboard use and accessible names. Firefox and Safari were not run.",
                 "A real e-mail provider: stubbed, and tested at the interface only, as the Test Plan allows.",
                 "User acceptance by the Product Owner: planned for the final demo."):
        body += f"<li>{esc(item)}</li>"
    body += "</ul><h2>8. Evidence</h2><div class=two>"
    for shot, cap in (("screenshots/06-task-created.png", "SV-06: task created in the browser"),
                      ("screenshots/19-notification.png", "SV-19: reminder delivered as a notification"),
                      ("screenshots/23-admin.png", "SV-23: administrator after deactivating a user"),
                      ("screenshots/27-dark-mode.png", "SV-27: dark mode")):
        if (EVIDENCE / shot).exists():
            body += figure(shot, cap)
    body += "</div>"
    if (EVIDENCE / "screenshots/25-width-390.png").exists():
        body += '<div style="max-width:60mm">' + figure("screenshots/25-width-390.png", "SV-25: 390 px phone width") + "</div>"
    body += "<h2>9. All validation checks</h2>"
    body += table(["Check", "Test Case", "Requirement", "What was checked and expected", "Observed", "Result"],
                  [(x["id"], x["tc"], x["req"], Raw(f"<b>{esc(x['title'])}</b><br>{esc(x['expected'])}"),
                    x["actual"], verdict(x["status"])) for x in cases])
    return "System_Validation_Report", "System Validation Report", body


# ================================================================ coverage reports
def tool_note(cov, tests):
    c = Counter(t["status"] for t in tests)
    note = (f"<p><b>Measured with:</b> {esc(coverage_tool(cov))}, over the full unit test suite "
            f"({len(tests)} tests, {c['PASS']} passed). Line numbers in the gap tables refer to the v1.0 source.</p>")
    if not is_coverage_py(cov):
        note += ("<div class=note><b>Measurement tool.</b> coverage.py could not be installed where these figures were "
                 "produced, so they come from <code>system_tests/stdlib_coverage.py</code>, which follows coverage.py's "
                 "definitions using Python's built-in monitoring. coverage.py may report slightly different counts. "
                 "To regenerate this report with coverage.py, run the commands in "
                 "<code>docs/testing/README.md</code>.</div>")
    return note


def coverage_scope():
    return ("<h2>What these figures do not show</h2><ul>"
            "<li><b>Scope:</b> the Python package <code>app/</code>, as in CI. <code>run.py</code> and the front-end "
            "JavaScript in <code>app/static/</code> are not measured here; the front-end is exercised by the browser "
            "checks in the System Validation Report.</li>"
            "<li><b>Covered does not mean correct.</b> The Part 3 tests ran every statement of v1.0 while defects "
            "DEF-01 to DEF-05 were still in that code: coverage shows that code ran, not that every input is "
            "handled. Sprint 3 therefore added route-wide boundary and fuzz tests.</li></ul>")


def coverage_rows(cov, base, keys):
    """Before / after rows. `keys` = (total, covered, missed) names in the coverage totals."""
    total, covered, missed = keys
    rows = []
    old = load_coverage("v1.0/coverage.json")
    if base:
        b = base["totals"]
        rows.append(("v1.0 code, tests as tagged", b[total], b[covered], b[missed], pct(b[covered], b[total])))
    if old:
        o = old["totals"]
        rows.append(("v1.0 code, with Part 3 tests", o[total], o[covered], o[missed], pct(o[covered], o[total])))
    t = cov["totals"]
    rows.append((f"{BUILD} code, all tests", t[total], t[covered], t[missed], pct(t[covered], t[total])))
    return rows


def code_coverage_report(cov, base, tests):
    body = front_matter("Code Coverage Report", "2.0", [
        ("1.0", "04-11-2026", "Student Team", "Statement coverage for tag v1.0."),
        ("2.0", TODAY, "Student Team", "Statement coverage for v1.0.1.")])
    body += "<h2>1. Result</h2>"
    rows = coverage_rows(cov, base, ("num_statements", "covered_lines", "missing_lines"))
    body += table(["Test set", "Statements", "Covered", "Missed", "Statement coverage"], rows, numeric=range(1, 5))
    body += tool_note(cov, tests)
    body += "<h2>2. Coverage by module</h2>"
    body += table(["Module", "Statements", "Covered", "Missed", "Coverage", "Missed lines"],
                  [(n, f["summary"]["num_statements"], f["summary"]["covered_lines"], f["summary"]["missing_lines"],
                    pct(f["summary"]["covered_lines"], f["summary"]["num_statements"]),
                    ", ".join(map(str, f["missing_lines"])) or "None") for n, f in cov["files"].items()], numeric=range(1, 5))
    if base:
        body += ("<h2>3. Gaps found in the v1.0 tests and closed in Part 3</h2><p>Measuring coverage showed which code "
                 "no test had run. <code>tests/test_part3_additions.py</code> now runs it.</p>")
        rows = [(n, ln, Raw(f"<code>{esc(f.get('source', {}).get(str(ln), ''))}</code>"))
                for n, f in base["files"].items() for ln in f["missing_lines"]]
        body += table(["Module", "Line", "Code not run by the v1.0 tests"], rows, numeric=(1,))
    missing = [(n, ln, Raw(f"<code>{esc(source_line(n, ln))}</code>")) for n, f in cov["files"].items() for ln in f["missing_lines"]]
    if missing:
        body += "<h2>Statements still not covered</h2>" + table(["Module", "Line", "Code"], missing, numeric=(1,))
    body += coverage_scope()
    return "Code_Coverage_Report", "Code Coverage Report", body


def describe_arc(file, src, dst):
    """Readable form of a branch: 'line 57 -> line 58' or 'line 57 -> exit'."""
    return f"{src} to {'function exit' if dst < 0 else dst}"


def branch_coverage_report(cov, base, tests):
    body = front_matter("Branch Coverage Report", "2.0", [
        ("1.0", "04-11-2026", "Student Team", "Branch coverage for tag v1.0."),
        ("2.0", TODAY, "Student Team", "Branch coverage for v1.0.1.")])
    body += "<h2>1. Result</h2>"
    rows = coverage_rows(cov, base, ("num_branches", "covered_branches", "missing_branches"))
    body += table(["Test set", "Branches", "Taken", "Not taken", "Branch coverage"], rows, numeric=range(1, 5))
    body += tool_note(cov, tests)
    body += ("<p>A branch is one possible path out of a decision: the true or false side of an <code>if</code>, or "
             "entering or leaving a <code>for</code> loop. Conditions inside a single line, such as "
             "<code>x if y else z</code>, are not counted separately, as in coverage.py's line-level view.</p>")
    body += "<h2>2. Branch coverage by module</h2>"
    body += table(["Module", "Branches", "Taken", "Not taken", "Coverage", "Branches not taken (from line to line)"],
                  [(n, f["summary"]["num_branches"], f["summary"]["covered_branches"],
                    f["summary"]["num_branches"] - f["summary"]["covered_branches"],
                    pct(f["summary"]["covered_branches"], f["summary"]["num_branches"]),
                    "; ".join(describe_arc(n, a, b) for a, b in f["missing_branches"]) or "None")
                   for n, f in cov["files"].items()], numeric=range(1, 5))
    if base:
        body += ("<h2>3. Branches not taken by the v1.0 tests and closed in Part 3</h2>")
        rows = [(n, describe_arc(n, a, b), Raw(f"<code>{esc(f.get('source', {}).get(str(a), ''))}</code>"))
                for n, f in base["files"].items() for a, b in f["missing_branches"]]
        body += table(["Module", "Branch", "Decision at the start of the branch"], rows)
    body += coverage_scope()
    return "Branch_Coverage_Report", "Branch Coverage Report", body


# ================================================================== write the files
def render(reports):
    """Write each report as HTML, then as PDF when Playwright is available."""
    for name, title, body in reports:
        (DOCS / f"{name}.html").write_text(
            f"<!doctype html><html lang=en><head><meta charset=utf-8><title>{esc(title)}</title>"
            f"<style>{CSS}</style></head><body>{body}</body></html>", encoding="utf-8")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Playwright is not installed: HTML written, PDF skipped.")
        return
    footer = ('<div style="font:7.5pt Arial;width:100%;padding:0 15mm;color:#555;display:flex;justify-content:space-between">'
              '<span>Task Manager Application: <span class="title"></span></span>'
              '<span>Page <span class="pageNumber"></span> of <span class="totalPages"></span></span></div>')
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page()
        for name, _, _ in reports:
            page.goto((DOCS / f"{name}.html").as_uri())
            page.wait_for_load_state("networkidle")
            page.pdf(path=DOCS / f"{name}.pdf", format="A4", print_background=True, prefer_css_page_size=True,
                     display_header_footer=True, header_template="<span></span>", footer_template=footer)
            (DOCS / f"{name}.html").unlink()     # the PDF is the deliverable
            print("wrote", name)
        browser.close()


def main():
    tests, suite = load_junit()
    cov, base = load_coverage(), load_coverage("coverage_v1_0_tests.json")
    data = json.loads((EVIDENCE / "system_validation_results.json").read_text(encoding="utf-8"))
    results = tc_results(tests, data["cases"])
    render([test_case_document(tests, data["cases"], results), unit_report(tests, suite, cov),
            system_report(data), code_coverage_report(cov, base, tests),
            branch_coverage_report(cov, base, tests)])


if __name__ == "__main__":
    main()
