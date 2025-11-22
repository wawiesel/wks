#!/usr/bin/env python3
"""Fix remaining broken file:// URLs by updating to correct paths."""

from pathlib import Path

VAULT_PATH = Path.home() / "_vault"

# Mapping of old broken paths to new correct paths
PATH_MAPPINGS = {
    "file:///Users/ww5/2024-A_GIS/": "file:///Users/ww5/2025-A_GIS/",
    "file:///Users/ww5/2024-OLM/": "file:///Users/ww5/2025-OLM/",
    "file:///Users/ww5/Documents/2025-PresentationArchive/ENDF81_Validation_NRC/": "file:///Users/ww5/2025-PresentationArchive/ENDF81_Validation_NRC/",
    "file:///Users/ww5/Documents/2025_09-DelayedNeutronPrecursors/": "file:///Users/ww5/Documents/2025_09-DelayedNeutronPrecursor/",
    "file:///Users/ww5/Documents/2024-NCSP_TPR/": "file:///Users/ww5/2024-NCSP_TPR/",
    "file:///Users/ww5/Documents/2024-NCSP_TPR/2024_12-NCSP_TPR_SCALE_rev5.pptx": "file:///Users/ww5/2024-NCSP_TPR/_drafts/2024_12-NCSP_TPR_SCALE_rev5.pptx",
}

# URLs to delete (path no longer exists)
DELETE_URLS = [
    "file:///Users/ww5/2025_10-SCALE_Manual_Chat/",
]


def fix_file(file_path: Path):
    """Fix file:// URLs in a single file."""
    content = file_path.read_text()
    original = content
    modified = False

    # Apply path mappings
    for old_url, new_url in PATH_MAPPINGS.items():
        if old_url in content:
            content = content.replace(old_url, new_url)
            modified = True
            print(f"  ✓ {old_url} → {new_url}")

    # Delete lines with URLs that no longer exist
    for delete_url in DELETE_URLS:
        if delete_url in content:
            lines = content.splitlines()
            new_lines = [line for line in lines if delete_url not in line]
            content = "\n".join(new_lines) + "\n"
            modified = True
            print(f"  🗑️  Removed line with: {delete_url}")

    if modified:
        file_path.write_text(content)
        return True
    return False


if __name__ == "__main__":
    files_to_fix = [
        VAULT_PATH / "_Past/2024-A_GIS.md",
        VAULT_PATH / "Projects/2024-OLM.md",
        VAULT_PATH / "People/Travis_Greene.md",
        VAULT_PATH / "People/Jesse_Brown.md",
        VAULT_PATH / "Topics/AI_ML/Building_SCALE_Models_with_AI.md",
        VAULT_PATH / "Topics/Nuclear_Data/ENDFB_VIII1_Release.md",
        VAULT_PATH / "Topics/Nuclear_Data/Delayed_Neutron_Precursors.md",
        VAULT_PATH / "Records/Meetings/NCSP_TPR.md",
        VAULT_PATH / "Organizations/INL/Horizontal_Split_Table.md",
    ]

    print("Fixing broken file:// URLs...")
    fixed_count = 0

    for file_path in files_to_fix:
        if not file_path.exists():
            print(f"⚠ Skip (not found): {file_path}")
            continue

        print(f"\n{file_path.relative_to(VAULT_PATH)}:")
        if fix_file(file_path):
            fixed_count += 1
            print(f"  → Updated")

    print(f"\n✓ Fixed {fixed_count} files")
    print("\nNow run the v2 script to convert remaining file:// to wiki-style links")
