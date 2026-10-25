# Changelog

## Unreleased
- `find`: searches every text file instead of a fixed extension list; binary files are detected and skipped.
- `find`: context windows of nearby hits are merged, so lines are no longer repeated and `--` only separates real gaps.
- `outline`: adds Go, Rust, Ruby, PHP, Java, Kotlin, C# and Swift; unsupported file types get a clear note instead of being parsed as JavaScript.
- `outline`: Python functions and classes inside `if`/`try`/`with`/`match` blocks are listed.
- `outline`: the line count no longer adds one for files ending in a newline.

## 0.1.0 — 2026-10-12
- First standalone release, split out of `localrat`.
- `find`: smart-case by default plus `case` option (`smart`, `sensitive`, `insensitive`); `word` option for whole-word matches; skips files ignored by `.gitignore` inside git repos; no trailing `--` separator with `context`.
- `outline`: Python ranges start at the first decorator; JS/TS detects `export default`, arrow functions and function expressions; shell and PowerShell list functions instead of `#` comments; Markdown ignores headings inside code fences.
