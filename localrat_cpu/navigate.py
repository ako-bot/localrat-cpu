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
TEXT_EXTS = {".py", ".js", ".ts", ".tsx", ".jsx", ".json", ".md", ".txt", ".toml", ".yml", ".yaml", ".html", ".css", ".sh", ".ps1", ".cfg", ".ini"}
MAX_FILE_BYTES = 1_000_000
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
        if path.suffix.lower() not in TEXT_EXTS or not path.match(glob):
            continue
        try:
            if path.is_file() and path.stat().st_size <= MAX_FILE_BYTES:
                yield path
        except OSError:
            continue


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
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue
        rel = path.relative_to(base).as_posix()
        for i, line in enumerate(lines):
            if not pattern.search(line):
                continue
            if hits >= max_hits:
                truncated = True
                break
            hits += 1
            if context and out:
                out.append("--")
            lo, hi = max(0, i - context), min(len(lines), i + context + 1)
            for j in range(lo, hi):
                mark = ":" if j == i else "-"
                out.append(f"{rel}:{j + 1}{mark} {lines[j].strip()[:MAX_LINE_CHARS]}")
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

    visit(tree, 0)
    return rows


_JS = re.compile(
    r"^\s*(?:export\s+(?:default\s+)?)?(?:async\s+)?(?:function\*?\s*\w*\s*\(|class\s+\w+)"
    r"|^\s*(?:export\s+)?(?:const|let|var)\s+\w+\s*=\s*(?:async\s+)?(?:function\b|\([^)]*\)\s*=>|\w+\s*=>)"
)
_SHELL = re.compile(r"^\s*(?:function\s+[\w-]+|[\w-]+\s*\(\)\s*\{)")
_PS1 = re.compile(r"^\s*(?:function|filter)\s+[\w-]+", re.IGNORECASE)
_MD = re.compile(r"^#{1,6}\s+\S")
_PATTERNS = {
    ".js": _JS, ".jsx": _JS, ".ts": _JS, ".tsx": _JS,
    ".sh": _SHELL, ".ps1": _PS1, ".md": _MD,
}


def outline(file: str) -> str:
    """List top-level structure of one file with line numbers."""
    path = Path(file).resolve()
    if not path.is_file():
        return f"[ERROR] file not found: {path}"
    text = path.read_text(encoding="utf-8", errors="ignore")
    total = text.count("\n") + 1
    suffix = path.suffix.lower()
    if suffix == ".py":
        try:
            rows = _outline_python(text)
        except SyntaxError as exc:
            return f"[ERROR] syntax error at line {exc.lineno}: {exc.msg}"
    else:
        pattern = _PATTERNS.get(suffix, _JS)
        in_fence = False
        rows = []
        for n, line in enumerate(text.splitlines(), 1):
            if suffix == ".md" and line.lstrip().startswith(("```", "~~~")):
                in_fence = not in_fence
                continue
            if not in_fence and pattern.match(line):
                rows.append(f"{n} {line.strip()[:MAX_LINE_CHARS]}")
    header = f"{path.name} ({total} lines)"
    return header + "\n" + ("\n".join(rows) if rows else "(no functions, classes or headings found)")
