# Special Directory Structures

## Presentation Archives

**Location:** `~/Documents/YYYY-PresentationArchive/`

**Structure:**
```
~/Documents/2024-PresentationArchive/
  Presentation_Name/
    Presentation_Name.pptx
    Presentation_Name.md

~/Documents/2025-PresentationArchive/
  Presentation_Name/
    Presentation_Name.pptx
    Presentation_Name.md
```

**Rules:**
- Flat structure: each presentation in its own directory directly under year archive
- Directory name = presentation name (short, descriptive)
- Markdown conversion: Use `docling file.pptx --to md` to convert to markdown
- Store markdown alongside original presentation with same basename
- Extract author and title from markdown (typically in first 10 lines)
- Create People pages in `~/_vault/People/` for each author
- Link presentations to authors' People pages

**Pre-2024 archives:**
- Move to `~/_old/YYYY-PresentationArchive/`
- Keeps current archives focused on recent work

## Email Archives

**Location:** `~/Documents/2025-Emails/`

**Subdirectories:**
- `NRC/` - Nuclear Regulatory Commission correspondence
- `ORNL/` - Internal ORNL communications
- `DNCSH/` - DOE-NE Domestic Nuclear Capabilities Strategic Hub
- `Personal/` - Professional personal correspondence
- `Conferences/` - Conference and meeting related emails

**Naming:** `YYYY_MM_DD-Subject-Correspondent.pdf`

## Meeting Transcripts

**Location:** `~/Documents/2025-MeetingTranscripts/`

**Purpose:** AI-generated meeting transcripts from Granola and similar services

**Naming:** `YYYY_MM_DD-Meeting_Title-Attendees.format`

**Formats:** PDF (preferred), Markdown, DOCX, TXT, JSON
