"""Format monitor status data for display."""


def _status_format(data: dict) -> list[dict]:
    """Format monitor status data for table display."""
    tables = []

    # Main status table
    main_table_data = [
        {"Metric": "Tracked Files", "Value": str(data.get("tracked_files", 0))},
    ]
    if data.get("issues"):
        main_table_data.append({"Metric": "Issues", "Value": str(len(data["issues"]))})
    if data.get("redundancies"):
        main_table_data.append({"Metric": "Redundancies", "Value": str(len(data["redundancies"]))})

    tables.append({"data": main_table_data, "headers": ["Metric", "Value"], "title": "Monitor Status"})

    # Issues table
    if data.get("issues"):
        issues_data = [{"Issue": issue} for issue in data["issues"]]
        tables.append({"data": issues_data, "headers": ["Issue"], "title": "Configuration Issues"})

    # Redundancies table
    if data.get("redundancies"):
        redundancies_data = [{"Redundancy": redundancy} for redundancy in data["redundancies"]]
        tables.append({"data": redundancies_data, "headers": ["Redundancy"], "title": "Redundancies"})

    # Managed directories table
    if data.get("managed_directories"):
        managed_dirs_data = []
        for path, info in data["managed_directories"].items():
            if isinstance(info, dict):
                priority = info.get("priority", "N/A")
                valid = "✓" if info.get("valid", False) else "✗"
                error = info.get("error", "")
                managed_dirs_data.append(
                    {"Path": path, "Priority": str(priority), "Valid": valid, "Error": error if error else "-"}
                )
            else:
                # Legacy format: just priority number
                managed_dirs_data.append({"Path": path, "Priority": str(info), "Valid": "-", "Error": "-"})
        tables.append(
            {
                "data": managed_dirs_data,
                "headers": ["Path", "Priority", "Valid", "Error"],
                "title": "Managed Directories",
            }
        )

    # Include/Exclude paths table
    include_paths = data.get("include_paths", [])
    exclude_paths = data.get("exclude_paths", [])
    if include_paths or exclude_paths:
        paths_data = []
        for path in include_paths:
            paths_data.append({"Type": "Include", "Path": path})
        for path in exclude_paths:
            paths_data.append({"Type": "Exclude", "Path": path})
        if paths_data:
            tables.append({"data": paths_data, "headers": ["Type", "Path"], "title": "Path Rules"})

    # Include/Exclude dirnames table
    include_dirnames = data.get("include_dirnames", [])
    exclude_dirnames = data.get("exclude_dirnames", [])
    if include_dirnames or exclude_dirnames:
        dirnames_data = []
        for dirname in include_dirnames:
            dirnames_data.append({"Type": "Include", "Directory Name": dirname})
        for dirname in exclude_dirnames:
            dirnames_data.append({"Type": "Exclude", "Directory Name": dirname})
        if dirnames_data:
            tables.append(
                {
                    "data": dirnames_data,
                    "headers": ["Type", "Directory Name"],
                    "title": "Directory Name Rules",
                }
            )

    # Include/Exclude globs table
    include_globs = data.get("include_globs", [])
    exclude_globs = data.get("exclude_globs", [])
    if include_globs or exclude_globs:
        globs_data = []
        for glob in include_globs:
            globs_data.append({"Type": "Include", "Glob Pattern": glob})
        for glob in exclude_globs:
            globs_data.append({"Type": "Exclude", "Glob Pattern": glob})
        if globs_data:
            tables.append({"data": globs_data, "headers": ["Type", "Glob Pattern"], "title": "Glob Pattern Rules"})

    return tables

