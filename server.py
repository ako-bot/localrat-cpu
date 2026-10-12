import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP

# Ensure localrat_cpu package is importable
CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from localrat_cpu import navigate

# CPU-only tools: no model, no tokens spent per query
mcp = FastMCP("localrat-cpu")


@mcp.tool()
def find(query: str, root: str = ".", glob: str = "*", regex: bool = False,
         context: int = 0, max_hits: int = 30, case: str = "smart", word: bool = False) -> str:
    """
    Search the repo with pure CPU (zero tokens, no model). Returns `path:line: text`.
    Use instead of ls/grep/exploratory reads. `glob` filters files (e.g. "*.py"),
    `context` adds lines around each hit, `max_hits` caps the output.
    `case`: "smart" (default; case-insensitive unless the query has uppercase),
    "sensitive" or "insensitive". `word=True` matches whole words only.
    Files ignored by .gitignore are skipped inside git repos.
    """
    return navigate.find(query, root, glob, regex, context, max_hits, case, word)


@mcp.tool()
def outline(file: str) -> str:
    """
    Structure of one file with pure CPU: functions and classes (with line ranges) or headings.
    Use before reading a whole file; then read only the range you need.
    """
    return navigate.outline(file)


if __name__ == "__main__":
    mcp.run()
