# AST Engine

A small, pluggable static-analysis engine for Python, built on the standard-library `ast` module. No third-party dependencies.

## Install

```bash
pip install -e ".[dev]"
```

## Use

```bash
ast-engine check src/                       # analyze files or folders
ast-engine check src/ --format json         # machine-readable output
ast-engine check src/ --select AST001,AST002
ast-engine check src/ --ignore AST004 --max-complexity 15
ast-engine rules                            # list rules
ast-engine dump file.py                     # print a file's AST (useful for writing rules)
```

Exit code is `1` when issues are found, `0` otherwise. Silence a line with `# noqa` or `# noqa: AST001,AST004`.

## Built-in rules

| Code   | Name                 | What it flags |
|--------|----------------------|---------------|
| AST000 | (engine)             | Syntax errors and unreadable files |
| AST001 | bare-except          | `except:` with no exception type |
| AST002 | mutable-default      | `def f(x=[])` and friends |
| AST003 | unused-import        | Imported names never used |
| AST004 | print-call           | `print()` calls (info) |
| AST005 | compare-to-singleton | `== None`, `!= True` etc. |
| AST006 | high-complexity      | Cyclomatic complexity above `--max-complexity` (10) |
| AST007 | too-many-arguments   | More than `--max-args` (6) parameters |

## Writing a rule

```python
import ast
from ast_engine import Rule, register

@register
class NoEval(Rule):
    code = "X100"
    name = "no-eval"
    description = "Avoid eval()."

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Name) and node.func.id == "eval":
            self.report(node, "`eval()` is dangerous")
        self.generic_visit(node)
```

A rule is an `ast.NodeVisitor`. Implement `visit_<NodeType>` methods, call `self.report(node, message)`, and optionally override `finish()` for whole-module checks.

## Layout

```
src/ast_engine/
  engine.py      file discovery, parsing, rule execution, noqa handling
  models.py      Finding and Severity
  rules/base.py  Rule base class and registry
  rules/builtin.py  built-in rules
  reporters.py   text and JSON output
  cli.py         command-line interface
tests/
```
