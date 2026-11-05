"""
Line and branch coverage using only the Python standard library (sys.monitoring, Python 3.12+).

Normally you should use the real tool:
    pytest --cov=app --cov-branch

This script exists for machines where coverage.py cannot be installed. It runs pytest, then
writes a JSON file with the same shape as `coverage json`, so report generation works with either.

How it counts, following coverage.py's definitions as closely as possible:
  * A STATEMENT is an AST statement that produces bytecode. A multi-line statement counts once.
  * A statement is covered when the interpreter ran any line of its header.
  * A BRANCH is a jump from one statement to one of two or more possible next statements:
    `if` true/false and `for` enter/exit. Conditions inside one line (x if y else z) are not
    counted, which is the same as coverage.py's line-level view.

Usage (from the repository root):
    python system_tests/stdlib_coverage.py OUT.json -- <pytest arguments>
"""

import ast
import dis
import json
import opcode
import os
import sys
import types
from pathlib import Path

MON = sys.monitoring
TOOL_ID = 3
APP_DIR = str(Path.cwd() / "app")
EXIT = -1                                  # the "leaves this code object" destination
# Instructions that are part of a loop's exit and carry the `for` line number.
_LOOP_CLEANUP = {"END_FOR", "POP_TOP", "POP_ITER", "NOP", "NOT_TAKEN"}

hit_lines, hit_arcs, offset_maps = {}, {}, {}


def offsets_to_lines(code):
    """{bytecode offset: source line} for one code object."""
    table = {}
    for start, end, line in code.co_lines():
        for offset in range(start, end, 2):
            table[offset] = line
    return table


def destination_line(code, src_line, dst_offset, table):
    """Source line reached by a jump, skipping loop clean-up code still on the jump's own line."""
    instructions = offset_maps.setdefault(("ins", code),
                                          {i.offset: i for i in dis.get_instructions(code)})
    offset = dst_offset
    while offset in table:
        line, ins = table[offset], instructions.get(offset)
        if line is not None and (line != src_line or ins is None or ins.opname not in _LOOP_CLEANUP):
            return line
        offset += 2
    return EXIT


def on_line(code, line):
    if not code.co_filename.startswith(APP_DIR):
        return MON.DISABLE
    hit_lines.setdefault(code.co_filename, set()).add(line)
    return None


def on_branch(code, src_offset, dst_offset):
    if not code.co_filename.startswith(APP_DIR):
        return MON.DISABLE
    table = offset_maps.setdefault(code, offsets_to_lines(code))
    src = table.get(src_offset)
    if src is not None:
        dst = destination_line(code, src, dst_offset, table)
        hit_arcs.setdefault(code.co_filename, set()).add((src, dst))
    return None


def code_objects(code):
    yield code
    for const in code.co_consts:
        if isinstance(const, types.CodeType):
            yield from code_objects(const)


def statement_map(tree):
    """{source line: first line of the statement whose header contains that line}."""
    owner = {}
    docstrings = set()
    for node in ast.walk(tree):
        scopes = (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        if isinstance(node, scopes) and node.body:
            first = node.body[0]
            if (isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant)
                    and isinstance(first.value.value, str)):
                docstrings.add(first)
    # ast.walk is breadth-first, so an inner statement overwrites its enclosing header.
    for node in ast.walk(tree):
        if not isinstance(node, ast.stmt) or node in docstrings:
            continue
        start = min([node.lineno] + [d.lineno for d in getattr(node, "decorator_list", [])])
        body = getattr(node, "body", None)
        end = body[0].lineno - 1 if isinstance(body, list) and body else node.end_lineno
        for line in range(start, max(start, end) + 1):
            owner[line] = start
    return owner


def analyse(path):
    source = Path(path).read_text(encoding="utf-8")
    owner = statement_map(ast.parse(source))
    executable, possible = set(), {}
    for code in code_objects(compile(source, path, "exec", dont_inherit=True)):
        table = offsets_to_lines(code)
        executable |= {owner[line] for _, _, line in code.co_lines() if line in owner}
        for ins in dis.get_instructions(code):
            if not ins.opname.startswith(("POP_JUMP_IF", "FOR_ITER")):
                continue
            src = table.get(ins.offset)
            if src is None or src not in owner:
                continue
            caches = opcode._inline_cache_entries.get(ins.opname, 0)
            if isinstance(caches, dict):              # newer Pythons name each cache entry
                caches = sum(caches.values())
            for dst_offset in (ins.offset + 2 + 2 * caches, ins.argval):
                dst = destination_line(code, src, dst_offset, table)
                dst = owner.get(dst, dst)
                if dst != owner[src]:
                    possible.setdefault(owner[src], set()).add(dst)
    branches = {(src, dst) for src, dsts in possible.items() if len(dsts) > 1 for dst in dsts}
    ran = {owner[line] for line in hit_lines.get(path, ()) if line in owner}
    taken = {(owner.get(a, a), owner.get(b, b)) for a, b in hit_arcs.get(path, ())}
    missing_branches = sorted(branches - taken)
    return {
        "summary": {"num_statements": len(executable), "missing_lines": len(executable - ran),
                    "covered_lines": len(executable & ran), "num_branches": len(branches),
                    "covered_branches": len(branches & taken), "missing_branches": len(missing_branches),
                    "num_partial_branches": len({a for a, _ in missing_branches if a in ran})},
        "missing_lines": sorted(executable - ran),
        "missing_branches": [list(b) for b in missing_branches],
    }


def main():
    out_path, pytest_args = sys.argv[1], sys.argv[3:]
    MON.use_tool_id(TOOL_ID, "stdlib_coverage")
    MON.register_callback(TOOL_ID, MON.events.LINE, on_line)
    MON.register_callback(TOOL_ID, MON.events.BRANCH, on_branch)
    MON.set_events(TOOL_ID, MON.events.LINE | MON.events.BRANCH)
    sys.path.insert(0, os.getcwd())
    import pytest                               # imported after monitoring is on
    exit_code = pytest.main(pytest_args)
    MON.set_events(TOOL_ID, 0)

    files = {f"app/{p.name}": analyse(str(p)) for p in sorted(Path(APP_DIR).glob("*.py"))}
    keys = ("num_statements", "missing_lines", "covered_lines", "num_branches", "covered_branches",
            "missing_branches", "num_partial_branches")
    totals = {k: sum(f["summary"][k] for f in files.values()) for k in keys}
    Path(out_path).write_text(json.dumps({
        "meta": {"tool": "system_tests/stdlib_coverage.py (Python sys.monitoring)",
                 "python": sys.version.split()[0], "branch_coverage": True},
        "files": files, "totals": totals}, indent=1), encoding="utf-8")
    print(f"statements {totals['num_statements']}, missing {totals['missing_lines']}; "
          f"branches {totals['num_branches']}, covered {totals['covered_branches']}")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
