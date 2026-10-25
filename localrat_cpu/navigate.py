"""CPU-only repository navigation: zero tokens, zero model calls.

find()    -> compact `path:line: text` hits for a literal or regex query.
outline() -> functions, classes and headings of one file with their lines.
"""
import ast
import os
import re
import subprocess
from pathlib import Path

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build", ".mypy_cache", ".pytest_cache"}
MAX_FILE_BYTES = 1_000_000
BINARY_SNIFF_BYTES = 8192
MAX_LINE_CHARS = 200
CASE_MODES = {"smart", "sensitive", "insensitive"}


def _git_files(root: Path) -> list[Path] | None:
    """Tracked + untracked-but-not-ignored files under `root`, or None outside a git repo."""
    try:
        res = subprocess.run(
            ["git", "-C", str(root), "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
            capture_output=True, timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if res.returncode != 0:
        return None
    names = res.stdout.decode("utf-8", errors="ignore").split("\0")
    return sorted(root / name for name in dict.fromkeys(names) if name)


def _walk_files(root: Path):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for name in sorted(filenames):
            yield Path(dirpath) / name


def _iter_files(root: Path, glob: str):
    candidates = _git_files(root)
    if candidates is None:
        candidates = _walk_files(root)
    for path in candidates:
        if SKIP_DIRS.intersection(path.relative_to(root).parts[:-1]):
            continue
        if not path.match(glob):
            continue
        try:
            if path.is_file() and path.stat().st_size <= MAX_FILE_BYTES:
                yield path
        except OSError:
            continue


def _read_lines(path: Path) -> list[str] | None:
    """Lines of a text file, or None if it is binary (NUL byte in its head) or unreadable."""
    try:
        with path.open("rb") as fh:
            head = fh.read(BINARY_SNIFF_BYTES)
            if b"\0" in head:
                return None
            data = head + fh.read()
    except OSError:
        return None
    return data.decode("utf-8", errors="ignore").splitlines()


def _hit_blocks(rel: str, lines: list[str], matches: list[int], context: int) -> list[list[str]]:
    """Hit lines with their context; overlapping or adjacent windows merge into one block."""
    spans: list[list[int]] = []
    for i in matches:
        lo, hi = max(0, i - context), min(len(lines), i + context + 1)
        if spans and lo <= spans[-1][1]:
            spans[-1][1] = max(spans[-1][1], hi)
        else:
            spans.append([lo, hi])
    hit_set = set(matches)
    return [
        [f"{rel}:{j + 1}{':' if j in hit_set else '-'} {lines[j].strip()[:MAX_LINE_CHARS]}" for j in range(lo, hi)]
        for lo, hi in spans
    ]


def _compile(query: str, regex: bool, case: str, word: bool) -> re.Pattern:
    body = query if regex else re.escape(query)
    if word:
        body = rf"(?<!\w)(?:{body})(?!\w)"
    ignore_case = case == "insensitive" or (case == "smart" and query == query.lower())
    return re.compile(body, re.IGNORECASE if ignore_case else 0)


def find(query: str, root: str = ".", glob: str = "*", regex: bool = False,
         context: int = 0, max_hits: int = 30, case: str = "smart", word: bool = False) -> str:
    """Search text files under `root`. Returns at most `max_hits` hits.

    case: "smart" (insensitive unless the query has an uppercase letter),
          "sensitive" or "insensitive".
    word: match whole words only.
    Inside a git repo, files ignored by .gitignore are skipped.
    """
    base = Path(root).resolve()
    if not base.exists():
        return f"[ERROR] path not found: {base}"
    if case not in CASE_MODES:
        return f"[ERROR] invalid case mode: {case!r} (use smart, sensitive or insensitive)"
    try:
        pattern = _compile(query, regex, case, word)
    except re.error as exc:
        return f"[ERROR] invalid regex: {exc}"

    out, hits, truncated = [], 0, False
    for path in _iter_files(base, glob):
        lines = _read_lines(path)
        if lines is None:
            continue
        matches = []
        for i, line in enumerate(lines):
            if not pattern.search(line):
                continue
            if hits >= max_hits:
                truncated = True
                break
            hits += 1
            matches.append(i)
        for block in _hit_blocks(path.relative_to(base).as_posix(), lines, matches, context):
            if context and out:
                out.append("--")
            out.extend(block)
        if truncated:
            break
    if not out:
        return f"No matches for {query!r} under {base}"
    if truncated:
        out.append(f"[truncated at {max_hits} hits; narrow the query or glob]")
    return "\n".join(out)


def _outline_python(source: str) -> list[str]:
    tree = ast.parse(source)
    rows: list[str] = []

    def visit(node, depth):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                kind = "class" if isinstance(child, ast.ClassDef) else "def"
                start = min([d.lineno for d in child.decorator_list] + [child.lineno])
                end = getattr(child, "end_lineno", child.lineno)
                rows.append(f"{'  ' * depth}{start}-{end} {kind} {child.name}")
                visit(child, depth + 1)
            elif isinstance(child, (ast.stmt, ast.excepthandler, ast.match_case)):
                # defs inside if/try/with/for/match blocks keep the enclosing depth
                visit(child, depth)

    visit(tree, 0)
    return rows


_JS = re.compile(
    r"^\s*(?:export\s+(?:default\s+)?)?(?:async\s+)?(?:function\*?\s*\w*\s*\(|class\s+\w+)"
    r"|^\s*(?:export\s+)?(?:const|let|var)\s+\w+\s*=\s*(?:async\s+)?(?:function\b|\([^)]*\)\s*=>|\w+\s*=>)"
)
_SHELL = re.compile(r"^\s*(?:function\s+[\w-]+|[\w-]+\s*\(\)\s*\{)")
_PS1 = re.compile(r"^\s*(?:function|filter)\s+[\w-]+", re.IGNORECASE)
_MD = re.compile(r"^#{1,6}\s+\S")
_GO = re.compile(r"^(?:func\s|type\s+\w+\s+(?:struct|interface)\b)")
_RUST = re.compile(r"^\s*(?:pub(?:\([^)]*\))?\s+)?(?:(?:async|const|unsafe)\s+)*(?:fn|struct|enum|trait|impl|mod|union)\b")
_RUBY = re.compile(r"^\s*(?:def|class|module)\s")
_PHP = re.compile(r"^\s*(?:(?:abstract|final|public|private|protected|static|readonly)\s+)*(?:function|class|interface|trait|enum)\s+&?\w")
# Java, Kotlin, C#, Swift: type declarations, fun/func, and methods with at least one modifier
_CLIKE = re.compile(
    r"^\s*(?:(?:public|private|protected|internal|static|final|abstract|sealed|open|override|virtual"
    r"|async|suspend|data|inline|partial|readonly)\s+)*(?:class|interface|enum|record|struct|object|fun|func)\s+\w"
    r"|^\s*(?:(?:public|private|protected|internal|static|final|abstract|override|virtual|async|synchronized)\s+)+"
    r"[\w<>\[\],.?]+(?:\s+[\w<>\[\],.?]+)*\s+\w+\s*\("
)
_PATTERNS = {
    ".js": _JS, ".jsx": _JS, ".ts": _JS, ".tsx": _JS, ".mjs": _JS, ".cjs": _JS, ".mts": _JS, ".cts": _JS,
    ".sh": _SHELL, ".bash": _SHELL, ".zsh": _SHELL, ".ps1": _PS1, ".psm1": _PS1,
    ".md": _MD, ".markdown": _MD,
    ".go": _GO, ".rs": _RUST, ".rb": _RUBY, ".php": _PHP,
    ".java": _CLIKE, ".kt": _CLIKE, ".kts": _CLIKE, ".cs": _CLIKE, ".swift": _CLIKE,
}


def outline(file: str) -> str:
    """List top-level structure of one file with line numbers."""
    path = Path(file).resolve()
    if not path.is_file():
        return f"[ERROR] file not found: {path}"
    text = path.read_text(encoding="utf-8", errors="ignore")
    header = f"{path.name} ({len(text.splitlines())} lines)"
    suffix = path.suffix.lower()
    if suffix == ".py":
        try:
            rows = _outline_python(text)
        except SyntaxError as exc:
            return f"[ERROR] syntax error at line {exc.lineno}: {exc.msg}"
    elif suffix not in _PATTERNS:
        return f"{header}\n(outline not supported for {suffix or 'files without extension'}; use find)"
    else:
        pattern = _PATTERNS[suffix]
        in_fence = False
        rows = []
        for n, line in enumerate(text.splitlines(), 1):
            if pattern is _MD and line.lstrip().startswith(("```", "~~~")):
                in_fence = not in_fence
                continue
            if not in_fence and pattern.match(line):
                rows.append(f"{n} {line.strip()[:MAX_LINE_CHARS]}")
    return header + "\n" + ("\n".join(rows) if rows else "(no functions, classes or headings found)")
