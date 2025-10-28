# Wieselquist Knowledge System (WKS)

**Version:** 1.1
**Updated:** 2025-10-28
**Author:** William Wieselquist
**Purpose:** Complete specification and AI assistant instructions for the Wieselquist Knowledge System

## Table of Contents

1. [System Overview](#system-overview)
2. [Core Principles](#core-principles)
3. [Critical Rules](#critical-rules)
4. [File System Structure](#file-system-structure)
5. [Naming Conventions](#naming-conventions)
6. [Special Directory Structures](#special-directory-structures)
7. [Obsidian Vault Organization](#obsidian-vault-organization)
8. [Common Workflows](#common-workflows)
9. [AI Agent Guidelines](#ai-agent-guidelines)

---

## System Overview

The Wieselquist Knowledge System (WKS) is an AI-assisted file organization and knowledge management system that uses Obsidian as an intelligent layer for maintaining connections and organization across a structured file system.

## Core Principles

1. **Date-based naming** encodes temporal scope and relevance
2. **Hierarchical archiving** (`_old/YYYY/`) keeps workspaces clean
3. **Obsidian as intelligent layer** maintains connections as files move
4. **Desktop as focus workspace** - curated via symlinks
5. **AI agent maintains coherence** between filesystem and knowledge graph

## Critical Rules

### Obsidian Linking Policy

**NEVER link to obsidian from outside obsidian. Obsidian manages the links of our data.**

- External files (in `~/YYYY-projectname/`, `~/Documents/`, etc.) should NOT contain links to `~/obsidian/` files
- Only Obsidian vault files may link to other Obsidian vault files
- Links flow: Obsidian → Filesystem (one-way)
- Obsidian notes can reference filesystem locations
- Filesystem content remains link-free

### Naming Convention Rules

**Year-only directories DO NOT use `_XX` suffix:**

- ❌ Wrong: `2025_XX-NRC_Misc`
- ✅ Correct: `2025-NRC_Misc`

**Month/Day directories use underscores in date portion:**

- Month-scoped: `YYYY_MM-DocumentName` (e.g., `2024_08-QuarterlyReport`)
- Day-scoped: `YYYY_MM_DD-DeadlineName` (e.g., `2025_03_15-ProposalDue`)

**Name format guidelines:**

- Single hyphen (`-`) separates date from name
- No additional hyphens within namestring
- Use underscores or PascalCase for multi-word names
- Example: `2025-SCALE_Validation` or `2025-ScaleValidation`

## Special Directory Structures

### Presentation Archives

Location: `~/Documents/YYYY-PresentationArchive/`

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
- Create People pages in `~/obsidian/People/` for each author
- Link presentations to authors' People pages

**Pre-2024 archives:**
- Move to `~/_old/YYYY-PresentationArchive/`
- Keeps current archives focused on recent work

### Email Archives

Location: `~/Documents/2025-Emails/`

**Subdirectories:**
- `NRC/` - Nuclear Regulatory Commission correspondence
- `ORNL/` - Internal ORNL communications
- `DNCSH/` - DOE-NE Domestic Nuclear Capabilities Strategic Hub
- `Personal/` - Professional personal correspondence
- `Conferences/` - Conference and meeting related emails

**Naming:** `YYYY_MM_DD-Subject-Correspondent.pdf`

### Meeting Transcripts

Location: `~/Documents/2025-MeetingTranscripts/`

**Purpose:** AI-generated meeting transcripts from Granola and similar services

**Naming:** `YYYY_MM_DD-Meeting_Title-Attendees.format`

**Formats:** PDF (preferred), Markdown, DOCX, TXT, JSON

## Obsidian Vault Organization

### Structure

- **Projects/** - One note per `~/YYYY-projectname/` directory
- **People/** - Collaborators, contacts, professional relationships
- **Topics/** - Technical domains (reactor physics, nuclear data, SCALE)
- **Organizations/** - ORNL, NRC, DOE, universities
- **Records/** - Trip reports, performance reviews, meetings
- **Index.md** - Main dashboard

### Obsidian Vault (`~/obsidian/`)

Knowledge graph and organizational layer containing:
- Project descriptions and status
- Links to filesystem locations
- Relationships between projects/people/topics
- Ideas that may become projects
- Meeting notes and trip reports

**Key capability:** Maintains coherence as filesystem evolves

**Symlink structure:** `~/obsidian/_links/` mirrors home directory, containing symlinks to selected files. Internal to vault for managing embedded content.

**Note on refreshing:** External file modifications may require manual refresh (Cmd+R) in Obsidian. Edits within Obsidian refresh automatically.

### Linking Strategy

- **Bidirectional links** between related concepts
- **MOCs (Maps of Content)** for major areas
- **Tags** for cross-cutting themes (#validation, #proposal, #publication)
- **Dataview queries** for dynamic collections

### Page Templates

**People Pages** (`~/obsidian/People/`)

```markdown
# [Full Name]
**Position:** [Title]
**Organization:** [ORNL/NRC/etc.]
**Expertise:** [Primary areas]

## Collaboration
[Projects worked on together]

## Related
- [[Projects/ProjectName]]
```

Create when: author on presentations, collaborator on projects, frequent correspondent.

**Projects Pages** (`~/obsidian/Projects/`)

```markdown
# [Project Name]
**Status:** Active/Completed/On Hold
**Started:** YYYY-MM
**Directory:** `~/YYYY-projectname/`

## Overview
[Purpose and goals]

## People
- [[People/PersonName]]

## Topics
- [[Topics/TopicName]]
```

**Topics Pages** (`~/obsidian/Topics/`)

Create for: technical subjects spanning multiple projects, domain knowledge areas, cross-cutting methodologies.

---

## AI Agent Guidelines

### File Operation Preferences

**ALWAYS prefer editing existing files over creating new ones**

Exceptions: User explicitly requests new file, no relevant file exists, creating structured Obsidian content.

**Use specialized tools:**
- **Read** not `cat`, `head`, `tail`
- **Edit** not `sed`, `awk`
- **Write** not `echo >` or `cat <<EOF`
- **Glob** not `find`, `ls`
- **Grep** not `grep`, `rg`

Reserve Bash for actual system commands (git, npm, docker).

### Task Management

**Use TodoWrite tool for:**
- Multi-step tasks (3+ steps)
- Complex/non-trivial operations
- User provides multiple tasks
- Tracking progress across session

**Task states:** `pending`, `in_progress` (only ONE at a time), `completed`

**Critical:** Mark tasks completed IMMEDIATELY upon finishing, not in batches.

**Don't use for:** Single straightforward tasks, trivial operations, informational requests.

### Agent Responsibilities

**Filesystem → Obsidian:**
- Detect new projects → create Project notes
- Monitor file movements → update links
- Identify related content → suggest connections

**Obsidian → Filesystem:**
- New idea note with detail → create project directory
- Deadline approaching → surface on Desktop
- Project archived → consider filesystem archival

**Maintenance:**
- Suggest archiving stale content to `_old/YYYY/`
- Identify misplaced files
- Maintain Index.md dashboard
- Clean up broken links

**Knowledge Discovery:**
- Find connections between new and old work
- Surface relevant archived projects
- Suggest collaborators based on topic overlap

## Common Workflows

### New Project Setup

1. Create directory: `~/YYYY-ProjectName/`
2. Create Obsidian note: `~/obsidian/Projects/YYYY-ProjectName.md`
3. Link to related People and Topics
4. Update `~/obsidian/Index.md` if major project
5. Consider Desktop symlink if immediate focus

### Document Organization

1. Verify document is finalized (not working draft)
2. Place in `~/Documents/YYYY_MM-DocumentName/`
3. Working drafts/code go in project directories
4. Old/reference-only material → `~/_old/`

### Archiving Content

When project/content becomes inactive:
1. Create `_old/YYYY/` in appropriate location
2. Move content maintaining structure
3. Update Obsidian links if referenced
4. Don't break existing paths

### Desktop Curation

Desktop contains only:
- 3-5 symlinks to active projects
- Symlinks to imminent deadlines
- Critical files needing immediate attention

Remove symlinks when focus shifts.

### Git Commits

Only create commits when user explicitly requests.

**Format:**
```
Brief summary

- file1: changes
- file2: changes

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
```

**Always use HEREDOC:**
```bash
git commit -m "$(cat <<'EOF'
Summary
- Details
🤖 Generated with [Claude Code](https://claude.com/claude-code)
Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
```

### Large File Handling

Large files may exceed Read tool limits (256KB):
- Use `offset` and `limit` parameters with Read
- Use Grep to extract specific sections
- Author info typically in first 10-30 lines

---

*Operational guidelines for AI assistants working with the Wieselquist Knowledge System*
