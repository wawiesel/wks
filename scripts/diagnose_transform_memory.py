#!/usr/bin/env python3
"""Diagnose memory usage of transform domain imports.

This script measures the memory footprint of importing transform-related
modules to identify what's contributing to OOM during mutation testing.

Usage:
    python scripts/diagnose_transform_memory.py
"""

import gc


def get_memory_mb() -> float:
    """Get current process memory in MB (RSS)."""
    try:
        import resource

        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024  # macOS returns KB
    except Exception:
        # Fallback for Linux
        try:
            with open("/proc/self/status") as f:
                for line in f:
                    if line.startswith("VmRSS:"):
                        return int(line.split()[1]) / 1024  # KB to MB
        except Exception:
            return 0.0


def measure_import(module_name: str, baseline: float) -> float:
    """Import a module and return memory delta."""
    gc.collect()
    before = get_memory_mb()
    try:
        __import__(module_name)
        gc.collect()
        after = get_memory_mb()
        delta = after - baseline
        print(f"  {module_name}: {delta:+.1f} MB (total: {after:.1f} MB)")
        return after
    except ImportError as e:
        print(f"  {module_name}: IMPORT ERROR - {e}")
        return before


def main():
    print("=" * 60)
    print("Transform Domain Memory Analysis")
    print("=" * 60)

    gc.collect()
    baseline = get_memory_mb()
    print(f"\nBaseline (Python interpreter): {baseline:.1f} MB\n")

    # Core Python imports
    print("--- Core Python ---")
    current = measure_import("hashlib", baseline)
    current = measure_import("pathlib", baseline)
    current = measure_import("json", baseline)

    # Heavy dependencies
    print("\n--- Heavy Dependencies ---")
    current = measure_import("pydantic", baseline)
    current = measure_import("pymongo", baseline)

    # Transform domain
    print("\n--- Transform Domain ---")
    current = measure_import("wks.api.transform", baseline)
    current = measure_import("wks.api.transform._TransformController", baseline)
    current = measure_import("wks.api.transform._get_engine_by_type", baseline)

    # Tree-sitter base
    print("\n--- Tree-Sitter ---")
    current = measure_import("tree_sitter", baseline)
    current = measure_import("wks.api.transform._treesitter._language_registry", baseline)

    # Individual tree-sitter languages
    print("\n--- Tree-Sitter Languages (lazy load on first use) ---")
    languages = [
        "tree_sitter_python",
        "tree_sitter_javascript",
        "tree_sitter_typescript",
        "tree_sitter_json",
        "tree_sitter_yaml",
        "tree_sitter_markdown",
        "tree_sitter_bash",
        "tree_sitter_c",
        "tree_sitter_cpp",
        "tree_sitter_java",
        "tree_sitter_go",
        "tree_sitter_rust",
        "tree_sitter_ruby",
        "tree_sitter_php",
        "tree_sitter_html",
        "tree_sitter_css",
        "tree_sitter_toml",
    ]
    for lang in languages:
        current = measure_import(lang, baseline)

    # Docling (if available)
    print("\n--- Docling ---")
    current = measure_import("docling", baseline)

    # Sentence transformers (if available)
    print("\n--- Sentence Transformers ---")
    current = measure_import("sentence_transformers", baseline)

    # PyTorch (loaded by sentence_transformers)
    print("\n--- PyTorch ---")
    current = measure_import("torch", baseline)

    print("\n" + "=" * 60)
    gc.collect()
    final = get_memory_mb()
    print(f"Final memory: {final:.1f} MB")
    print(f"Total growth: {final - baseline:.1f} MB")
    print("=" * 60)


if __name__ == "__main__":
    main()
