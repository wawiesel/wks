# WKS Quick Walkthrough

This walkthrough shows the shortest useful path through WKS: configure it, monitor a file, sync a vault, transform a document, and search the index.

## 1. Configure

Create `~/.wks/config.json` with valid sections for:

- `monitor`
- `database`
- `service`
- `daemon`
- `vault`
- `log`
- `transform`
- `cat`

Reset if you want a clean start:

```bash
wksc database reset all
```

## 2. Monitor a File

```bash
wksc monitor check ~/Desktop
wksc monitor sync ~/Desktop/test_note.md
wksc monitor status
```

Use `monitor check` to understand why a path is or is not included. Use `monitor sync` to write current file state into the database.

## 3. Run the Daemon

```bash
wksc daemon start --restrict ~/Desktop/wks_test
wksc daemon status
```

The daemon watches for changes and syncs them automatically.

## 4. Sync the Vault

```bash
wksc vault sync
wksc vault check
wksc vault links vault:///note.md
```

Vault commands scan notes, track links, and check for broken references.

## 5. Transform a Document

```bash
wksc cat ~/Documents/example.pdf
wksc transform engine textpass ~/notes/example.txt
```

Transforms materialize cached content under the configured transform cache and expose it through `cat` and related command flows.

## 6. Build and Query an Index

```bash
wksc index main ~/Desktop/test_note.md
wksc search "test note"
```

If the configured index has embeddings, the same query surface can support semantic search.

## 7. Use MCP or REST

Equivalent capabilities are also available through:

- the MCP server for agent-facing tool use
- the read-only REST server for HTTP clients

```bash
wksm
wksr --host 127.0.0.1 --port 8765
```
