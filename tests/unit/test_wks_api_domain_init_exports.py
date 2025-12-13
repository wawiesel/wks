"""Contract: domain __init__.py exports only <Domain><Cmd>Output names derived from cmd_*.py files."""

from __future__ import annotations

import importlib
from pathlib import Path


def _camel(s: str) -> str:
    return "".join(part.capitalize() for part in s.split("_") if part)


def test_domain_init_all_exports_only_outputs() -> None:
    api_dir = Path(__file__).resolve().parents[2] / "wks" / "api"

    for domain_dir in sorted(api_dir.iterdir(), key=lambda p: p.name):
        if not domain_dir.is_dir():
            continue
        init_py = domain_dir / "__init__.py"
        if not init_py.exists():
            continue

        init_text = init_py.read_text(encoding="utf-8")
        if "register_from_schema" not in init_text and "SchemaLoader.register_from_schema" not in init_text:
            continue

        domain = domain_dir.name
        expected = []
        for cmd_file in sorted(domain_dir.glob("cmd_*.py")):
            cmd_name = cmd_file.stem[len("cmd_") :]
            expected.append(f"{domain.capitalize()}{_camel(cmd_name)}Output")
        expected = sorted(expected)

        mod = importlib.import_module(f"wks.api.{domain}")
        assert hasattr(mod, "__all__")
        assert sorted(list(mod.__all__)) == expected

        for name in expected:
            assert hasattr(mod, name)
