# WKS Quick Walkthrough

Shortest path: configure, sync one path, transform a document, search it, then expose the same system through MCP or REST.

## Configure

Create `~/.wks/config.json` with valid `monitor`, `database`, `service`, `daemon`, `vault`, `log`, `transform`, and `cat` sections.

```bash
wksc database reset all
```

## Monitor a File

```bash
wksc monitor check ~/Desktop
wksc monitor sync ~/Desktop/test_note.md
```

## Run the Daemon

```bash
wksc daemon start --restrict ~/Desktop/wks_test
wksc daemon status
```

## Sync the Vault

```bash
wksc vault sync
wksc vault check
wksc vault links vault:///note.md
```

## Transform a Document

```bash
wksc cat ~/Documents/example.pdf
wksc transform engine textpass ~/notes/example.txt
```

## Build and Query an Index

```bash
wksc index main ~/Desktop/test_note.md
wksc search "test note"
```

## Use MCP or REST

```bash
wksm
wksr --host 127.0.0.1 --port 8765
```
