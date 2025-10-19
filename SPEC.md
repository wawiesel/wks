# Wieselquist Knowledge System (WKS) Specification

**Version:** 1.0
**Created:** 2025-10-19
**Author:** William Wieselquist

## Overview

The Wieselquist Knowledge System (WKS) is an AI-assisted file organization and knowledge management system that uses Obsidian as an intelligent layer for maintaining connections and organization across a structured file system.

## Core Principles

1. **Date-based naming** encodes temporal scope and relevance
2. **Hierarchical archiving** (`_old/YYYY/`) keeps workspaces clean
3. **Obsidian as intelligent layer** maintains connections as files move
4. **Desktop as focus workspace** - curated weekly via symlinks
5. **AI agent maintains coherence** between filesystem and knowledge graph

## File System Structure

```
~/
├── YYYY-ProjectName/               # Active projects (year-scoped)
│   ├── [project files]
│   └── _old/                       # Project-specific archive
│       └── YYYY/                   # Year-organized old content
│
├── deadlines/
│   └── YYYY_MM_DD-DeadlineName/    # Time-sensitive deliverables
│       └── _old/
│           └── YYYY/
│
├── Documents/
│   └── YYYY_MM-DocumentName/       # Finalized reference materials
│       └── _old/
│           └── YYYY/
│
├── obsidian/                       # Knowledge management vault
│   ├── Projects/                   # Project tracking and links
│   ├── People/                     # Collaborators, contacts
│   ├── Topics/                     # Technical subjects, domains
│   ├── Ideas/                      # Nascent concepts, brainstorms
│   ├── Organizations/              # ORNL, NRC, etc.
│   └── Index.md                    # Main dashboard
│
├── Desktop/                        # Weekly focus (symlinks only)
│
└── Downloads/                      # Temporary staging area
```

## Naming Conventions

**Format:** `DATESTRING-namestring`

- **Separator:** Single hyphen (`-`) between date and name
- **Name format:** No hyphens within namestring (use underscores or capitalization for readability)
- **Preferred style:** PascalCase or snake_case for multi-word names
- **Not allowed:** Additional hyphens within namestring (only one hyphen total, separating date from name)

### Date String Formats

| Format | Scope | Use Case | Example |
|--------|-------|----------|---------|
| `YYYY-` | Year | Projects, long-term work | `2025-SCALE_Validation` |
| `YYYY_MM-` | Month | Documents, reports | `2024_06-QuarterlyReport` |
| `YYYY_MM_DD-` | Day | Deadlines, events | `2025_03_15-ProposalDue` |

**Date Semantics:**
- For **projects**: Year the project is active
- For **documents**: Month/year document was finalized (not created or downloaded)
- For **deadlines**: The actual deadline date

## Directory Types and Purposes

### Projects (`~/YYYY-projectname/`)

Active work directories containing:
- Code, scripts, analysis
- Working drafts and documents
- Meeting notes (or links to obsidian notes)
- Project-specific data and outputs

**Archiving:** When portions become obsolete → `_old/YYYY/`

### Deadlines (`~/deadlines/YYYY_MM_DD-deadlinename/`)

Time-sensitive deliverables with specific due dates:
- Proposals
- Reports with submission deadlines
- Grant applications
- Conference paper submissions

**Lifecycle:** After deadline passes → move to appropriate project or `_old/YYYY/`

### Documents (`~/Documents/YYYY_MM-documentname/`)

Static reference materials:
- Contracts and agreements
- Published papers (others' work)
- Specifications and standards
- Final reports (received, not created)

**Not for:** Working drafts, active code, things you're creating

### Obsidian Vault (`~/obsidian/`)

Knowledge graph and organizational layer containing:
- Project descriptions and status
- Links to filesystem locations
- Relationships between projects/people/topics
- Ideas that may become projects
- Meeting notes and trip reports

**Key capability:** Maintains coherence as filesystem evolves

**Symlink structure:** The `~/obsidian/links/` directory mirrors the home directory structure, containing symlinks to selected files from projects. This allows embedding external files while preserving original names and paths.

**Note on refreshing:** When external tools or agents modify symlinked files, Obsidian may require a manual refresh (Cmd+R) to update embedded views. Edits made within Obsidian automatically refresh.

## Archive Pattern

Every major directory can contain `_old/` for aging out content:

```
~/2025-projectname/
  ├── [active content]
  └── _old/
      ├── 2024/          # Content from 2024
      │   └── [old files]
      └── 2023/          # Content from 2023
          └── [old files]
```

**When to archive:**
- Content no longer actively used
- Superseded by newer versions
- Historical reference only
- Keep workspace focused on current work

## Obsidian Structure and Organization

### Folder Organization

- **Projects/** - One note per project, linking to `~/YYYY-projectname/` directories
- **People/** - Collaborators, contacts, professional relationships
- **Topics/** - Technical domains (reactor physics, nuclear data, SCALE, etc.)
- **Ideas/** - Nascent concepts that may become projects
- **Organizations/** - ORNL, NRC, DOE, universities, etc.
- **Records/** - Trip reports, performance reviews, meetings

### Linking Strategy

- **Bidirectional links** between related concepts
- **MOCs (Maps of Content)** for major areas
- **Tags** for cross-cutting themes (#validation, #proposal, #publication)
- **Dataview queries** for dynamic collections (active projects, upcoming deadlines)

### Index.md Structure

Main dashboard showing:
- Active projects (from `~/YYYY-*` directories)
- Upcoming deadlines (from `~/deadlines/`)
- Recent updates
- Key areas of focus
- Quick links to major topics

## Desktop Workflow

**Purpose:** Weekly focus workspace with curated symlinks

**Setup:**
1. Each week (or as needed), refresh Desktop with:
   - Symlinks to 3-5 active projects
   - Symlinks to imminent deadlines
   - Critical files needing attention

2. Desktop should be **ephemeral** - not permanent storage

3. At end of week/task:
   - Remove symlinks that are no longer focus areas
   - Clean up any loose files to proper homes

**Agent role:** Help curate what belongs on Desktop based on priorities

## AI Agent Responsibilities

The AI agent (Claude Code or specialized agent) maintains system coherence:

### 1. Filesystem → Obsidian Updates

- Detect new project directories → create Project notes
- Monitor file movements → update links
- Identify related content → suggest connections
- Track project completion → suggest archiving

### 2. Obsidian → Filesystem Actions

- New idea note with sufficient detail → create project directory
- Recognize connections → link to relevant old projects
- Deadline approaching → surface on Desktop
- Project note archived → consider filesystem archival

### 3. Organization Maintenance

- Suggest archiving stale content to `_old/YYYY/`
- Identify misplaced files
- Recommend directory restructuring
- Maintain Index.md dashboard
- Clean up broken links

### 4. Knowledge Discovery

- Find connections between new and old work
- Surface relevant archived projects
- Suggest collaborators based on topic overlap
- Identify duplicate or related efforts

## Migration from Stacks

The previous "stacks" system used hierarchical markdown files (`_trunk.node.md`, `_branch.node.md`, `_leaf.node.md`) for organization.

**Migration strategy:**

1. **Content extraction:**
   - Trip reports → `~/Documents/YYYY_MM-tripname/` + Obsidian notes
   - Active projects → `~/YYYY-projectname/`
   - Old projects → appropriate `_old/YYYY/` locations
   - Technical notes → Obsidian Topics/

2. **Organizational content:**
   - Organizations (ORNL, NRC) → Obsidian Organizations/
   - Science categories (reactor-physics, nuclear-data) → Obsidian Topics/
   - Personal records → Obsidian Records/

3. **Symlinks and scaffolding:**
   - Remove `_trunk`, `_branch`, `_leaf` files
   - Remove symlinks from vault to stacks
   - Delete organizational scaffolding

4. **Scripts:**
   - Move incomplete scripts from `~/bin/` to `~/2025-WKS/bin/`
   - Document original intent
   - Evaluate for integration into new system

## Desktop and Downloads Cleanup

**Current state:** Loose files need organization

**Process:**
1. Identify file purpose and project association
2. Route to appropriate location:
   - Working files → relevant `~/YYYY-projectname/`
   - Reference docs → `~/Documents/YYYY_MM-documentname/`
   - Time-sensitive → `~/deadlines/YYYY_MM_DD-deadlinename/`
   - Obsolete → `_old/YYYY/` or delete

3. Create Obsidian notes as needed for tracking

## System Maintenance

### Weekly Review
- Update Desktop symlinks to current focus
- Process Downloads folder
- Update Obsidian Index.md
- Archive completed work

### Monthly Review
- Evaluate project status
- Archive stale content to `_old/`
- Update knowledge connections
- Review and update WKS spec

### Annual Review
- Move completed projects to `_old/`
- Archive old deadlines
- Consolidate Documents
- System cleanup and optimization

## Future Enhancements

Potential future capabilities:
- Automated deadline reminders
- Project status tracking and reporting
- Time allocation tracking
- Publication and presentation pipeline
- Integration with external systems (git, calendar, email)
- Multi-user collaboration patterns

## Implementation Notes

**Phase 1: Foundation**
- Create directory structure
- Establish Obsidian vault organization
- Document specification (this file)

**Phase 2: Migration**
- Extract content from stacks
- Organize Desktop and Downloads
- Initial Obsidian population

**Phase 3: Agent Development**
- Define agent workflows
- Implement monitoring and maintenance
- Test and refine automation

**Phase 4: Iteration**
- Use system in practice
- Identify pain points
- Refine based on actual usage

---

## Change Log

- **2025-10-19:** Initial specification created
