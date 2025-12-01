## Priority 1

Make MCP consistent with CLI for all commands through "diff" in @SPEC.md.

- wks_config
- wks_monitor
- wks_vault
- wks_transform
- wks_cat
- wks_diff

There should be no code that is not used by the MCP or CLI. There should be 100% code coverage in unit tests. There should be smoke tests for the MCP and CLI. 
Follow @CONTRIBUTING.md for contribution guidelines.
Follow @.cursor/rules/important.mdc for important rules.

## Priority 2

Refactor code to remove duplication and have better structure.
Delete all unused code.

It seems like we should be able to have a basic code organization like this:

# thin shims
wks/cli.py
wks/mcp.py

and then accessible via wks.<x> where <x> is something like "transform" or "monitor" for one of the main layers and then for the layers which have engines or other types of variants, you'd have something like wks.transform.docling. or wks.diff.meyers

Rename the command line `wksc` instead of `wks0`. 

Rename the MCP to `wksm_*` instead of `wks_*`.
## Priority 3

Revisit all the existing test code to make it more beautiful.

Tests should be simple and easy to read.
If the tests, pass then the capability referenced in @SPEC.md has been implemented successfully. If the tests fail then the capability referenced in @SPEC.md has not been implemented successfully. There must be logical equivalence between these. 
Do this only for the commands that are implemented, i.e. not index, search, or patterns.

## Priority 4

Implement the commands of index and search.

## Priority 5

Implement the patterns capability.