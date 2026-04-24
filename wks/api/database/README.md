# Database API

The database package provides backend-neutral persistence for WKS domains.

## Rules

- Command wrappers stay thin.
- Backend details stay isolated in backend-specific modules.
- Output contracts are defined in Python alongside the commands.
