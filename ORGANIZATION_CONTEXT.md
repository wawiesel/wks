# WKS Organization Context

This document preserves organizational decisions and context across sessions.

Last updated: 2025-10-19 (evening session)

## Current Organization Session (2025-10-19 Evening)

### Scope
Organizing files in ~/Desktop and ~/Downloads according to WKS principles.

### Key Decisions Made This Session

1. **Status reports are completed outputs, NOT works in progress**
   - DNCSH monthly status reports (to DOE) → `~/Documents/2025-DNCSH-Status/`
   - These are finished deliverables, not active work

2. **No loose files in Documents - everything must be in a directory**
   - Each presentation/file gets its own dated directory in Documents
   - Pattern: `~/Documents/YYYY_MM-EventName/` (even for single files)

3. **EPRI presentations are separate from status reports**
   - Created: `~/Documents/2025_02-EPRI_Presentation/` for EPRI presentations
   - These are distinct from DNCSH status reports

4. **Archive by project completion year, not discovery year**
   - NSED ModSim (2017-2018 meetings, last in Sept 2018) → `~/_old/2018/`
   - Rule: Archive based on when the project ended, not when you're organizing it

5. **Desktop/stacks migration philosophy**
   - Goal: Move FROM stacks organization TO WKS organization
   - Stacks is the old system being replaced

6. **Temporary file cleanup**
   - ChatGPT-generated images: Delete (generic AI illustrations)
   - Receipt photos (IMG-*, PXL-*, dated JPGs): Move to `~/Documents/2025-Trip-Receipts/`

### Completed Actions

1. ✓ Moved DNCSH FY25 status reports (Oct, Dec, Jan, Feb, Mar, Apr, Jun, Jul, Aug) to `~/Documents/2025-DNCSH-Status/`
2. ✓ Moved EPRI presentations (4 revisions) to `~/Documents/2025_02-EPRI_Presentation/`
3. ✓ Deleted Desktop screenshot (ChatGPT screen recording instructions)
4. ✓ Deleted ChatGPT-generated images from Downloads (8 files)
5. ✓ Created and moved trip receipt photos to `~/Documents/2025-Trip-Receipts/` (12 photos)
6. ✓ Archived NSED ModSim Strategic Plan to `~/_old/2018/NSED-ModSim-Strategic-Plan/`

### Project Structure (from previous session)

- **2025-DNCSH**: Monthly progress reports (1.03.01.02 format), DNCSH updates, quarterly PMPs
- **2025-NRC**: NRC program reviews, technical reports, SOWs, budget documents
- **2025-SCALE**: SCALE development, validation, quality initiatives, AI/ML applications

### File Categories Identified

#### DNCSH Files (2025-DNCSH project)
- Monthly reports: `1.03.01.02 DNCSH FY25 {Month}.pptx`
- Previous format: `1.02.07 DNCSH FY25 {Month}.pptx`
- Quarterly PMPs: `2025-Q{N}-PMPDNCSH_rev*.docx`
- Update presentations: `2024-12-10_DNCSH_Update_*.pptx`
- Supporting documents: `1.03.01.02 Supporting Document.docx`
- SPARC-related: `2025-dncsh-sparc.pptx`, `SPARC Off-Ramp Milestones_r2.pptx`

#### NRC Files (2025-NRC project)
- Program reviews: `00_Overview_SCALE_NRC_TPR_*.pptx`, `Agenda_NRC_Prog_Review_*.docx`
- SOWs: `1886-Z720-24 - NRC - SOW *.pdf/docx`
- Technical reports: `4_pwr_SURRY_*.docx`, `5_pwr_TP_*.docx`
- Budget: `2025-nrc-budgets.xlsx`
- Monthly reports: `31310025S0003 *.docx/pdf`

#### SCALE Files (2025-SCALE project)
- Quality: `2025_03_SCALE_Quality_Initiatives*.pptx`, `SCALE-QAP-005*.pdf`
- AI/ML: `14_2025-AI_ML_SCALE.pptx`
- Validation: `2024-SCALE63_RP_Validation/`
- General: `2024-SCALE_Past_Present_Future.pptx`, `232142_SCALE_overview.pdf`
- Benchmarking: `Criticality Benchmarking Project List.pdf`

#### Technical/Research Papers
- Should go to relevant projects or ~/Documents/Papers/

#### Personal Records
- Recommendations: Desktop/stacks/records/others/{year}-{person}/
- Insurance: `2025-Wieselquist-insurance-refusal.pdf`
- Photos: Personal/trip receipts

#### Screen Recordings & Screenshots
- Large screen recordings on Desktop (2025-07-03)
- Various screenshots in both locations
- Consider: Keep if documenting work, delete if obsolete

### Desktop/stacks Structure
```
stacks/
├── _inbox/          # Temporary holding for new items
├── organizations/   # ORNL, DOE organizational content
├── projects/        # Project-specific (may overlap with ~/YYYY-Project)
├── records/         # Personal records
│   ├── self/       # Personal performance, security, trips
│   └── others/     # Recommendations for others
└── science/        # (Not yet explored)
```

**Question**: How should stacks/ map to WKS structure?
- organizations/ → ~/Documents/Organizations/?
- records/self/ → ~/Documents/Personal/?
- records/others/ → ~/Documents/Recommendations/?
- projects/ → Merge into ~/YYYY-Project directories?

### Pending Decisions

1. What to do with large screen recordings (3.5GB total)?
2. Where to place Slack exports (`Reactorium_Slack_Export_2017_2024.zip`)?
3. How to handle duplicate files with rev numbers?
4. Treatment of build directories (build 1-9) in Downloads?
5. SCALE input/output files (.inp, .out, .f71, etc.) - keep or archive?

### Next Steps

1. Create project directories: ~/2025-DNCSH, ~/2025-NRC, ~/2025-SCALE
2. Move Desktop loose files
3. Organize Downloads by project
4. Archive 2024 content
5. Address Desktop/stacks reorganization (requires more context)

## Previous Sessions

### [Session Date - To Be Added]
Context about stacks/ reorganization - detailed plan existed but session closed.

## WKS Principles (from README.md)

- No loose files - everything in directories
- YYYY-ProjectName naming for project directories
- Appropriate placement: ~/, ~/Documents/, or ~/deadlines/
- Archive old content to _old/YYYY/
- Delete when appropriate - not everything needs archiving
