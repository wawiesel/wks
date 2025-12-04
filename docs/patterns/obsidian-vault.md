# Obsidian Vault Organization

## Structure

- **Projects/** - One note per `~/YYYY-projectname/` directory
- **People/** - Collaborators, contacts, professional relationships
- **Topics/** - Technical domains (reactor physics, nuclear data, SCALE)
- **Organizations/** - ORNL, NRC, DOE, universities
- **Records/** - Trip reports, performance reviews, meetings
- **Index.md** - Main dashboard

## Obsidian Vault (`~/_vault/`)

Knowledge graph and organizational layer containing:
- Project descriptions and status
- Links to filesystem locations
- Relationships between projects/people/topics
- Ideas that may become projects
- Meeting notes and trip reports

**Key capability:** Maintains coherence as filesystem evolves

**Symlink structure:** `~/_vault/_links/` mirrors home directory, containing symlinks to selected files. Internal to vault for managing embedded content.

**Note on refreshing:** External file modifications may require manual refresh (Cmd+R) in Obsidian. Edits within Obsidian refresh automatically.

## Linking Strategy

- **Bidirectional links** between related concepts
- **MOCs (Maps of Content)** for major areas
- **Tags** for cross-cutting themes (#validation, #proposal, #publication)
- **Dataview queries** for dynamic collections

## Page Templates

### People Pages (`~/_vault/People/`)

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

### Projects Pages (`~/_vault/Projects/`)

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

### Topics Pages (`~/_vault/Topics/`)

Create for: technical subjects spanning multiple projects, domain knowledge areas, cross-cutting methodologies.
