# localrat-cpu

**Zero-token code navigation for AI coding agents.** An MCP server with two tools that let an agent (Claude Code, Cursor, Codex…) find code without reading whole files. Pure CPU and Python standard library: no model, no index, no tokens spent per query.

[Leer en castellano](README.es.md)

## Why

Every file an agent opens costs tokens. Most exploratory reads exist only to answer "where is X?" or "what's in this file?". `find` and `outline` answer those questions with a few compact lines, so the agent reads only the range it actually needs.

## Tools

### `find`
Search text or regex across the repo. Returns `path:line: text`.

| Parameter | Default | Meaning |
|---|---|---|
| `query` | — | Text (or regex) to search for |
| `root` | `.` | Directory to search |
| `glob` | `*` | File filter, e.g. `*.py` |
| `regex` | `false` | Treat `query` as a regular expression |
| `context` | `0` | Lines of context around each hit |
| `max_hits` | `30` | Output cap |
| `case` | `smart` | `smart` (case-insensitive unless the query has uppercase), `sensitive`, `insensitive` |
| `word` | `false` | Whole-word matches only |

Inside a git repo, files ignored by `.gitignore` are skipped. Common build and dependency folders (`node_modules`, `.venv`, `dist`…) are always skipped.

```
find("AuthService", glob="*.py", word=True)
src/auth/service.py:12: class AuthService:
src/api/routes.py:4: from auth.service import AuthService
```

### `outline`
Structure of one file with line numbers.

- **Python**: functions and classes with `start-end` ranges (from the first decorator), nested methods indented. Uses `ast`.
- **JS/TS**: functions, classes, arrow functions, `export default`.
- **Shell / PowerShell**: function definitions (comments are not listed).
- **Markdown**: headings (ignoring code blocks).

```
outline("src/auth/service.py")
service.py (84 lines)
11-60 class AuthService
  14-30 def login
  32-60 def refresh
63-84 def hash_password
```

## Install

Requires Python 3.10+.

```bash
git clone https://github.com/<you>/localrat-cpu.git
cd localrat-cpu
pip install -r requirements.txt
```

Register it with Claude Code:

```bash
claude mcp add localrat-cpu -- python /absolute/path/to/localrat-cpu/server.py
```

Then add a line like this to your `CLAUDE.md` so the agent actually uses it:

```
To locate code, use the MCP tools `find` (path:line) and `outline` (functions with line ranges) before opening files; read only the ranges you need.
```

## Limits

- Searches files with common text extensions only (`.py`, `.js`, `.ts`, `.md`, `.json`, `.toml`, `.yml`, `.sh`, `.ps1`…); files over 1 MB are skipped.
- Non-Python outlines are regex-based: good enough to navigate, not a full parser, and without end lines.
- Search is pure Python. Fine for small and medium repos; on very large monorepos `ripgrep` will be faster.

## Tests

```bash
python -m unittest discover tests
```

## License

MIT
