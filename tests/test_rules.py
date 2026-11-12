import textwrap

import pytest

from ast_engine import Engine, Rule, register
from ast_engine.cli import main


def codes(src, **kw):
    return [f.code for f in Engine(**kw).check_source(textwrap.dedent(src), "mod.py")]


def test_bare_except():
    assert codes("try:\n    pass\nexcept:\n    pass\n") == ["AST001"]
    assert codes("try:\n    pass\nexcept ValueError:\n    pass\n") == []


@pytest.mark.parametrize("default", ["[]", "{}", "set()", "list()", "{1}"])
def test_mutable_default(default):
    assert codes(f"def f(x={default}):\n    return x\n") == ["AST002"]


def test_immutable_default_ok():
    assert codes("def f(x=None, y=(), z=1):\n    return x, y, z\n") == []


def test_unused_import():
    src = """
    import os
    import sys
    from typing import List, Dict
    from __future__ import annotations
    print(sys.argv)
    x: "Dict" = {}
    """
    found = Engine(select=["AST003"]).check_source(textwrap.dedent(src), "mod.py")
    assert sorted(f.message for f in found) == ["`List` imported but unused", "`os` imported but unused"]


def test_unused_import_respects_all_and_attributes():
    src = "import os.path\nimport json\n__all__ = ['json']\nos.path.join('a')\n"
    assert codes(src, select=["AST003"]) == []


def test_print_and_singleton():
    assert codes("print(1)\n") == ["AST004"]
    assert codes("x = 1\nif x == None: pass\nif x != True: pass\nif x == 0: pass\n") == ["AST005", "AST005"]


def test_complexity():
    body = "\n".join(f"    if x == {i}:\n        return {i}" for i in range(11))
    assert codes(f"def f(x):\n{body}\n") == ["AST006"]
    assert codes(f"def f(x):\n{body}\n", options={"max_complexity": 20}) == []


def test_too_many_args():
    assert codes("def f(a, b, c, d, e, f, g):\n    pass\n") == ["AST007"]
    assert codes("class C:\n    def m(self, a, b, c, d, e, f):\n        pass\n") == []


def test_select_ignore_and_noqa():
    src = "print(1)\ntry:\n    pass\nexcept:  # noqa: AST001\n    pass\n"
    assert codes(src) == ["AST004"]
    assert codes(src, ignore=["AST004"]) == []
    assert codes("print(1)  # noqa\n") == []


def test_syntax_error():
    assert codes("def broken(:\n") == ["AST000"]


def test_custom_rule():
    class NoEval(Rule):
        code = "X100"
        name = "no-eval"

        def visit_Call(self, node):
            if getattr(node.func, "id", None) == "eval":
                self.report(node, "eval is dangerous")
            self.generic_visit(node)

    engine = Engine(rules={"X100": register(NoEval)})
    assert [f.code for f in engine.check_source("eval('1')\n")] == ["X100"]


def test_cli(tmp_path, capsys):
    (tmp_path / "a.py").write_text("print('hi')\n")
    (tmp_path / "clean.py").write_text("x = 1\n")
    assert main(["check", str(tmp_path)]) == 1
    assert "AST004" in capsys.readouterr().out
    assert main(["check", str(tmp_path / "clean.py")]) == 0
    assert main(["check", "--format", "json", str(tmp_path)]) == 1
    assert '"code": "AST004"' in capsys.readouterr().out
    assert main(["rules"]) == 0
