# Changelog

## 0.1.0 — 2026-10-12
- First standalone release, split out of `localrat`.
- `find`: smart-case by default plus `case` option (`smart`, `sensitive`, `insensitive`); `word` option for whole-word matches; skips files ignored by `.gitignore` inside git repos; no trailing `--` separator with `context`.
- `outline`: Python ranges start at the first decorator; JS/TS detects `export default`, arrow functions and function expressions; shell and PowerShell list functions instead of `#` comments; Markdown ignores headings inside code fences.
