from __future__ import annotations

import argparse
import sys

from ast_engine import __version__
from ast_engine.engine import Engine
from ast_engine.reporters import REPORTERS
from ast_engine.rules.base import all_rules


def _codes(value: str) -> list[str]:
    return [c.strip() for c in value.split(",") if c.strip()]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ast-engine", description="Static analysis for Python built on the ast module.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check", help="Analyze files or directories")
    check.add_argument("paths", nargs="+", help="Files or directories to analyze")
    check.add_argument("--select", type=_codes, help="Only run these rule codes (prefixes allowed), comma-separated")
    check.add_argument("--ignore", type=_codes, help="Skip these rule codes (prefixes allowed), comma-separated")
    check.add_argument("--format", choices=sorted(REPORTERS), default="text")
    check.add_argument("--max-complexity", type=int, default=10)
    check.add_argument("--max-args", type=int, default=6)

    sub.add_parser("rules", help="List available rules")

    dump = sub.add_parser("dump", help="Print the AST of a file (handy when writing rules)")
    dump.add_argument("path")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "rules":
        for code, cls in all_rules().items():
            print(f"{code}  {cls.name:<22} {cls.severity.value:<8} {cls.description}")  # noqa: AST004
        return 0

    if args.command == "dump":
        import ast
        with open(args.path, encoding="utf-8") as fh:
            print(ast.dump(ast.parse(fh.read(), args.path), indent=2, include_attributes=False))  # noqa: AST004
        return 0

    engine = Engine(
        select=args.select,
        ignore=args.ignore,
        options={"max_complexity": args.max_complexity, "max_args": args.max_args},
    )
    findings = engine.check_paths(args.paths)
    print(REPORTERS[args.format](findings))  # noqa: AST004
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
