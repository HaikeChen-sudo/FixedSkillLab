"""A tiny deterministic tool-use environment with no model dependency."""

import argparse
import ast
import csv
import fnmatch
import json
import math
import operator
import shutil
import tempfile
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional

from skills import SKILLS, render as render_skill, validate_library
from tasks import TASKS, Task


class ToolError(ValueError):
    pass


TOOL_HELP = {
    "read_file": "read_file(path) -> UTF-8 text",
    "write_file": "write_file(path, content) -> characters written",
    "list_files": "list_files(path='.', pattern='*') -> sorted relative paths",
    "search_text": "search_text(query, path='.') -> matching file, line, and text records",
    "replace_text": "replace_text(path, old, new) -> replacement count",
    "calculate": "calculate(expression) -> arithmetic result",
    "convert_csv": "convert_csv(source, destination) -> JSON row count",
    "sort_data": "sort_data(source, destination, column, numeric=False, descending=False)",
    "filter_data": "filter_data(source, destination, column, operator, value, numeric=False)",
    "find_max": "find_max(source, column, numeric=False) -> largest value",
    "find_min": "find_min(source, column, numeric=False) -> smallest value",
    "sum_column": "sum_column(source, column) -> numeric sum",
    "count_rows": "count_rows(source) -> CSV data row count",
    "copy_file": "copy_file(source, destination) -> destination path",
    "move_file": "move_file(source, destination) -> destination path",
    "submit": "submit(value) -> record the task answer",
}


_BINARY_OPS: Dict[type, Callable[[Any, Any], Any]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY_OPS: Dict[type, Callable[[Any], Any]] = {ast.UAdd: operator.pos, ast.USub: operator.neg}


def _eval_arithmetic(node: ast.AST) -> Any:
    if isinstance(node, ast.Expression):
        return _eval_arithmetic(node.body)
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        return node.value
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
        return _UNARY_OPS[type(node.op)](_eval_arithmetic(node.operand))
    if isinstance(node, ast.BinOp) and type(node.op) in _BINARY_OPS:
        left, right = _eval_arithmetic(node.left), _eval_arithmetic(node.right)
        if isinstance(node.op, ast.Pow) and abs(right) > 12:
            raise ToolError("exponent is limited to 12")
        result = _BINARY_OPS[type(node.op)](left, right)
        if not isinstance(result, (int, float)) or not math.isfinite(result) or abs(result) > 10**15:
            raise ToolError("result is outside the allowed numeric range")
        return result
    raise ToolError("only numeric literals and arithmetic operators are allowed")


def _number(value: str) -> Any:
    number = float(value)
    return int(number) if number.is_integer() else number


def _submission_type(rules: List[Dict[str, Any]]) -> Optional[str]:
    """Expose only submit's JSON type, never its expected value."""
    for rule in rules:
        if rule["kind"] == "submission":
            value = rule["expected"]
            if value is None:
                return "null"
            if isinstance(value, bool):
                return "boolean"
            if isinstance(value, (int, float)):
                return "number"
            if isinstance(value, str):
                return "string"
            if isinstance(value, list):
                return "array"
            if isinstance(value, dict):
                return "object"
        if rule["kind"] == "all":
            found = _submission_type(rule["rules"])
            if found:
                return found
    return None


class MiniLab:
    """One isolated episode. Tools and graders are deterministic Python code."""

    def __init__(self, workspace: Optional[Path] = None):
        self._temp = tempfile.TemporaryDirectory(prefix="minilab-") if workspace is None else None
        self.root = Path(self._temp.name if self._temp else workspace).resolve()
        if self.root.exists() and any(self.root.iterdir()):
            raise ValueError(f"workspace must be empty: {self.root}")
        self.root.mkdir(parents=True, exist_ok=True)
        self.task: Optional[Task] = None
        self.submission: Any = None
        self.steps = 0

    def close(self) -> None:
        if self._temp:
            self._temp.cleanup()

    def __enter__(self) -> "MiniLab":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def reset(self, task_id: str) -> Dict[str, Any]:
        if task_id not in TASKS:
            raise KeyError(f"unknown task: {task_id}")
        for child in self.root.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
        self.task = TASKS[task_id]
        self.submission = None
        self.steps = 0
        for relative, content in self.task.files.items():
            path = self._path(relative)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        return {
            "task_id": self.task.id,
            "instruction": self.task.instruction,
            "success_condition": self.task.success,
            "answer_json_type": _submission_type(self.task.rules),
            "max_steps": self.task.max_steps,
            "tools": TOOL_HELP,
        }

    def call_tool(self, name: str, **args: Any) -> Any:
        if self.task is None:
            raise RuntimeError("call reset(task_id) first")
        if name not in TOOL_HELP:
            raise ToolError(f"unknown tool: {name}")
        if self.steps >= self.task.max_steps:
            raise ToolError(f"step limit reached ({self.task.max_steps})")
        self.steps += 1
        method = getattr(self, name)
        try:
            return method(**args)
        except TypeError as error:
            raise ToolError(f"invalid arguments for {name}: {error}") from error

    def grade(self) -> Dict[str, Any]:
        if self.task is None:
            raise RuntimeError("call reset(task_id) first")
        checks = [self._check(rule) for rule in self.task.rules]
        return {"success": all(checks), "checks": checks, "steps": self.steps}

    def _path(self, relative: str) -> Path:
        if not isinstance(relative, str) or not relative:
            raise ToolError("path must be a non-empty string")
        path = (self.root / relative).resolve()
        try:
            path.relative_to(self.root)
        except ValueError as error:
            raise ToolError("path escapes the workspace") from error
        return path

    def read_file(self, path: str) -> str:
        return self._path(path).read_text(encoding="utf-8")

    def write_file(self, path: str, content: str) -> int:
        target = self._path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        return target.write_text(content, encoding="utf-8")

    def list_files(self, path: str = ".", pattern: str = "*") -> List[str]:
        base = self._path(path)
        paths: Iterable[Path] = [base] if base.is_file() else base.rglob("*")
        return sorted(
            item.relative_to(self.root).as_posix()
            for item in paths
            if item.is_file() and fnmatch.fnmatch(item.name, pattern)
        )

    def search_text(self, query: str, path: str = ".") -> List[Dict[str, Any]]:
        if not query:
            raise ToolError("query must not be empty")
        base = self._path(path)
        paths = [base] if base.is_file() else sorted(item for item in base.rglob("*") if item.is_file())
        matches = []
        for file_path in paths:
            for line_number, line in enumerate(file_path.read_text(encoding="utf-8").splitlines(), 1):
                if query in line:
                    matches.append({
                        "path": file_path.relative_to(self.root).as_posix(),
                        "line": line_number,
                        "text": line,
                    })
        return matches

    def replace_text(self, path: str, old: str, new: str) -> int:
        if not old:
            raise ToolError("old text must not be empty")
        target = self._path(path)
        content = target.read_text(encoding="utf-8")
        count = content.count(old)
        target.write_text(content.replace(old, new), encoding="utf-8")
        return count

    def calculate(self, expression: str) -> Any:
        if len(expression) > 200:
            raise ToolError("expression is too long")
        try:
            tree = ast.parse(expression, mode="eval")
            return _eval_arithmetic(tree)
        except (SyntaxError, ZeroDivisionError, OverflowError) as error:
            raise ToolError(str(error)) from error

    def _read_csv(self, source: str) -> tuple:
        path = self._path(source)
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames:
                raise ToolError("CSV must have a header")
            return reader.fieldnames, list(reader)

    def _write_csv(self, destination: str, fields: List[str], rows: List[Dict[str, str]]) -> None:
        path = self._path(destination)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)

    @staticmethod
    def _require_column(fields: List[str], column: str) -> None:
        if column not in fields:
            raise ToolError(f"unknown column: {column}")

    def convert_csv(self, source: str, destination: str) -> int:
        _, rows = self._read_csv(source)
        path = self._path(destination)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return len(rows)

    def sort_data(
        self, source: str, destination: str, column: str,
        numeric: bool = False, descending: bool = False,
    ) -> int:
        fields, rows = self._read_csv(source)
        self._require_column(fields, column)
        key = (lambda row: float(row[column])) if numeric else (lambda row: row[column])
        rows.sort(key=key, reverse=descending)
        self._write_csv(destination, fields, rows)
        return len(rows)

    def filter_data(
        self, source: str, destination: str, column: str, operator: str,
        value: str, numeric: bool = False,
    ) -> int:
        fields, rows = self._read_csv(source)
        self._require_column(fields, column)
        operations = {
            "eq": operator_module.eq,
            "ne": operator_module.ne,
            "gt": operator_module.gt,
            "ge": operator_module.ge,
            "lt": operator_module.lt,
            "le": operator_module.le,
        }
        if operator not in operations:
            raise ToolError("operator must be one of eq, ne, gt, ge, lt, le")
        compare = operations[operator]
        expected: Any = float(value) if numeric else value
        kept = [row for row in rows if compare(float(row[column]) if numeric else row[column], expected)]
        self._write_csv(destination, fields, kept)
        return len(kept)

    def find_max(self, source: str, column: str, numeric: bool = False) -> Any:
        return self._extreme(source, column, numeric, max)

    def find_min(self, source: str, column: str, numeric: bool = False) -> Any:
        return self._extreme(source, column, numeric, min)

    def _extreme(self, source: str, column: str, numeric: bool, function: Callable) -> Any:
        fields, rows = self._read_csv(source)
        self._require_column(fields, column)
        if not rows:
            raise ToolError("CSV has no data rows")
        result = function(float(row[column]) if numeric else row[column] for row in rows)
        return _number(str(result)) if numeric else result

    def sum_column(self, source: str, column: str) -> Any:
        fields, rows = self._read_csv(source)
        self._require_column(fields, column)
        return _number(str(sum(float(row[column]) for row in rows)))

    def count_rows(self, source: str) -> int:
        return len(self._read_csv(source)[1])

    def copy_file(self, source: str, destination: str) -> str:
        target = self._path(destination)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(self._path(source), target)
        return target.relative_to(self.root).as_posix()

    def move_file(self, source: str, destination: str) -> str:
        target = self._path(destination)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(self._path(source)), str(target))
        return target.relative_to(self.root).as_posix()

    def submit(self, value: Any) -> Any:
        self.submission = value
        return value

    def _check(self, rule: Dict[str, Any]) -> bool:
        kind = rule["kind"]
        if kind == "all":
            return all(self._check(child) for child in rule["rules"])
        if kind == "submission":
            return self.submission == rule["expected"]
        path = self._path(rule["path"])
        if kind == "absent":
            return not path.exists()
        if not path.is_file():
            return False
        if kind == "text":
            return path.read_text(encoding="utf-8") == rule["expected"]
        if kind == "json":
            try:
                return json.loads(path.read_text(encoding="utf-8")) == rule["expected"]
            except (json.JSONDecodeError, UnicodeDecodeError):
                return False
        if kind == "csv":
            try:
                with path.open(newline="", encoding="utf-8") as handle:
                    return list(csv.DictReader(handle)) == rule["expected"]
            except (csv.Error, UnicodeDecodeError):
                return False
        raise ValueError(f"unknown grader rule: {kind}")


# The parameter is named operator in the public tool contract, so keep the module unshadowed here.
operator_module = operator


def self_check() -> Dict[str, Any]:
    failures = []
    with MiniLab() as lab:
        for task_id, task_item in TASKS.items():
            lab.reset(task_id)
            if lab.grade()["success"]:
                failures.append(f"{task_id}: passed before any actions")
                continue
            try:
                for item in task_item.reference:
                    lab.call_tool(item["tool"], **item["args"])
            except Exception as error:
                failures.append(f"{task_id}: reference error: {error}")
                continue
            if not lab.grade()["success"]:
                failures.append(f"{task_id}: reference did not pass")
    return {"success": not failures, "tasks": len(TASKS), "failures": failures}


def skill_check() -> Dict[str, Any]:
    errors = validate_library()
    return {"success": not errors, "skills": len(SKILLS), "failures": errors}


def _play(task_id: str, workspace: Optional[str]) -> int:
    lab = MiniLab(Path(workspace) if workspace else None)
    try:
        print(json.dumps(lab.reset(task_id), ensure_ascii=False, indent=2))
        print(f"workspace: {lab.root}")
        print('Enter one JSON action per line, for example {"tool":"read_file","args":{"path":"x.txt"}}')
        for line in iter(input, ""):
            request = json.loads(line)
            if request.get("grade"):
                print(json.dumps(lab.grade(), ensure_ascii=False))
                continue
            try:
                result = lab.call_tool(request["tool"], **request.get("args", {}))
                print(json.dumps({"ok": True, "result": result}, ensure_ascii=False))
            except (ToolError, OSError, KeyError, ValueError) as error:
                print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False))
    except (EOFError, KeyboardInterrupt):
        pass
    finally:
        print(json.dumps(lab.grade(), ensure_ascii=False))
        lab.close()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Deterministic Mini Lab for tool-using agents")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("list", help="list tasks")
    subparsers.add_parser("skills", help="list fixed skills; this does not activate one")
    show_skill = subparsers.add_parser("show-skill", help="show one fixed skill")
    show_skill.add_argument("skill_name", choices=SKILLS)
    show = subparsers.add_parser("show", help="show one task")
    show.add_argument("task_id", choices=TASKS)
    play = subparsers.add_parser("play", help="run the JSON-lines interactive protocol")
    play.add_argument("task_id", choices=TASKS)
    play.add_argument("--workspace", help="empty directory to preserve after the run")
    subparsers.add_parser("self-check", help="run all private reference actions")
    subparsers.add_parser("skill-check", help="validate the fixed skill library")
    args = parser.parse_args()

    if args.command == "list":
        for item in TASKS.values():
            print(f"{item.id}\t{item.instruction}")
        return 0
    if args.command == "skills":
        for item in SKILLS.values():
            print(f"{item.name}\t{item.description}")
        return 0
    if args.command == "show-skill":
        print(render_skill(SKILLS[args.skill_name]), end="")
        return 0
    if args.command == "show":
        item = TASKS[args.task_id]
        print(json.dumps({
            "id": item.id,
            "instruction": item.instruction,
            "success_condition": item.success,
            "max_steps": item.max_steps,
            "tools": TOOL_HELP,
        }, ensure_ascii=False, indent=2))
        return 0
    if args.command == "play":
        return _play(args.task_id, args.workspace)
    if args.command == "skill-check":
        result = skill_check()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["success"] else 1
    result = self_check()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
