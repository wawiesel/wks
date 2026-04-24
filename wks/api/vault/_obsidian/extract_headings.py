def extract_headings(text: str) -> dict[int, str]:
    headings: dict[int, str] = {}
    current_heading = ""

    for line_num, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if stripped.startswith("#"):
            current_heading = stripped.lstrip("#").strip()
        headings[line_num] = current_heading

    return headings
