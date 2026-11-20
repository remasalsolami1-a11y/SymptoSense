#!/usr/bin/env python3
"""Bilingual translation coverage gate for SymptoSense.

Checks:
- top-level literal AR/EN translation dictionaries keep identical key sets;
- values are non-empty strings/structures;
- suspicious long AR==EN strings are reported unless explicitly allowed;
- active medical KB rows have both Arabic and English required fields.

The script is dependency-light and is safe to run in CI before Flask imports.
"""
from __future__ import annotations
import ast
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGETS = {ROOT / "webapp.py": {"L", "CT"}, ROOT / "chat_view.py": {"CHAT"}}
IDENTICAL_ALLOW = {
    "SymptoSense", "English 🇬🇧", "العربية 🇸🇦", "Continue in English",
    "⬇ PDF", "© 2026 SymptoSense", "Designed & Developed by",
    "Remas Alsolami — Data Science Project", "Complete Blood Count (CBC)",
    "🩸 HbA1c", "🌙 Night Calm", "mg/dL", "mmol/L",
}


def literal_dicts(path: Path, names: set[str]):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id in names:
                try:
                    if (isinstance(node.value, ast.Call) and ast.unparse(node.value.func) == "inline_assets.data"):
                        import json
                        value = json.loads((ROOT / "inline_assets" / ast.literal_eval(node.value.args[0])).read_text(encoding="utf-8"))
                    else:
                        value = ast.literal_eval(node.value)
                except Exception as exc:
                    raise SystemExit(f"TRANSLATION CHECK FAIL: {path.name}:{target.id} is not statically inspectable: {exc}")
                yield target.id, value


def empty(value) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def check_static(errors: list[str], warnings: list[str]):
    for path, names in TARGETS.items():
        for name, data in literal_dicts(path, names):
            if not isinstance(data, dict) or not isinstance(data.get("ar"), dict) or not isinstance(data.get("en"), dict):
                errors.append(f"{path.name}:{name} must contain ar/en dictionaries")
                continue
            ar, en = data["ar"], data["en"]
            missing_en = sorted(set(ar) - set(en))
            missing_ar = sorted(set(en) - set(ar))
            if missing_en:
                errors.append(f"{path.name}:{name} missing EN keys: {missing_en[:20]}")
            if missing_ar:
                errors.append(f"{path.name}:{name} missing AR keys: {missing_ar[:20]}")
            for key in sorted(set(ar) & set(en)):
                if empty(ar[key]): errors.append(f"{path.name}:{name}.{key} has empty Arabic value")
                if empty(en[key]): errors.append(f"{path.name}:{name}.{key} has empty English value")
                if isinstance(ar[key], str) and isinstance(en[key], str):
                    a, e = ar[key].strip(), en[key].strip()
                    if a == e and len(a) >= 4 and a not in IDENTICAL_ALLOW:
                        warnings.append(f"{path.name}:{name}.{key} identical AR/EN: {a[:60]!r}")


def check_kb(errors: list[str]):
    db_path = ROOT / "symptosense.db"
    if not db_path.exists():
        return
    conn = sqlite3.connect(str(db_path))
    try:
        requirements = {
            "mk_symptoms": ("name_ar", "name_en", "description_ar", "description_en"),
            "mk_diseases": ("name_ar", "name_en", "description_ar", "description_en"),
            "mk_red_flags": ("name_ar", "name_en", "description_ar", "description_en", "message_ar", "message_en", "recommended_action_ar", "recommended_action_en"),
            "mk_sources": ("description_ar", "description_en"),
        }
        for table, cols in requirements.items():
            exists = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
            if not exists:
                continue
            for col in cols:
                n = conn.execute(
                    f"SELECT COUNT(*) FROM {table} WHERE COALESCE(status,'active')='active' AND TRIM(COALESCE({col},''))=''"
                ).fetchone()[0]
                if n:
                    errors.append(f"{table}.{col}: {n} active rows missing translation")
    finally:
        conn.close()


def main():
    errors, warnings = [], []
    check_static(errors, warnings)
    check_kb(errors)
    for w in warnings:
        print("TRANSLATION WARNING:", w)
    if errors:
        for e in errors:
            print("TRANSLATION ERROR:", e)
        raise SystemExit(1)
    print(f"TRANSLATION CHECK: PASS ({len(warnings)} warnings)")


if __name__ == "__main__":
    main()
