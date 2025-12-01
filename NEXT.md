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

## Priority 3

Implement remaining commands. 