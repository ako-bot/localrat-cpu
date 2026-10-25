import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from localrat_cpu import navigate


class NavigateTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "a.py").write_text(
            "import os\n\nclass Foo:\n    def bar(self):\n        return 1\n\ndef baz():\n    return 2\n",
            encoding="utf-8",
        )
        (self.root / "notes.md").write_text("# Title\ntext baz here\n## Sub\n", encoding="utf-8")
        (self.root / "node_modules").mkdir()
        (self.root / "node_modules" / "x.js").write_text("baz\n", encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def test_find_literal_skips_ignored_dirs(self):
        result = navigate.find("baz", str(self.root))
        self.assertIn("a.py:7: def baz():", result)
        self.assertIn("notes.md:2:", result)
        self.assertNotIn("node_modules", result)

    def test_find_glob_filters_files(self):
        result = navigate.find("baz", str(self.root), glob="*.py")
        self.assertIn("a.py", result)
        self.assertNotIn("notes.md", result)

    def test_find_context_and_truncation(self):
        result = navigate.find("a", str(self.root), max_hits=1)
        self.assertIn("[truncated at 1 hits", result)
        ctx = navigate.find("def baz", str(self.root), context=1)
        self.assertIn("a.py:6-", ctx)

    def test_find_no_match_and_bad_regex(self):
        self.assertIn("No matches", navigate.find("zzzz", str(self.root)))
        self.assertIn("invalid regex", navigate.find("(", str(self.root), regex=True))

    def test_outline_python_ranges(self):
        result = navigate.outline(str(self.root / "a.py"))
        self.assertIn("3-5 class Foo", result)
        self.assertIn("  4-5 def bar", result)
        self.assertIn("7-8 def baz", result)

    def test_outline_markdown_and_missing(self):
        self.assertIn("1 # Title", navigate.outline(str(self.root / "notes.md")))
        self.assertIn("file not found", navigate.outline(str(self.root / "nope.py")))

    def test_find_smart_case(self):
        (self.root / "c.py").write_text("class AuthService:\n    pass\nauthservice = 1\n", encoding="utf-8")
        upper = navigate.find("AuthService", str(self.root))
        self.assertIn("c.py:1:", upper)
        self.assertNotIn("c.py:3:", upper)
        lower = navigate.find("authservice", str(self.root))
        self.assertIn("c.py:1:", lower)
        self.assertIn("c.py:3:", lower)
        self.assertIn("c.py:3:", navigate.find("AuthService", str(self.root), case="insensitive"))
        self.assertNotIn("c.py:1:", navigate.find("authservice", str(self.root), case="sensitive"))
        self.assertIn("invalid case mode", navigate.find("x", str(self.root), case="bogus"))

    def test_find_whole_word(self):
        (self.root / "w.py").write_text("run()\nrunner()\n_run_all()\n", encoding="utf-8")
        result = navigate.find("run", str(self.root), glob="w.py", word=True)
        self.assertIn("w.py:1:", result)
        self.assertNotIn("w.py:2:", result)
        self.assertNotIn("w.py:3:", result)

    def test_find_context_has_no_trailing_separator(self):
        result = navigate.find("def baz", str(self.root), context=1)
        self.assertFalse(result.endswith("--"))

    def test_find_respects_gitignore(self):
        if shutil.which("git") is None:
            self.skipTest("git not installed")
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        (self.root / ".gitignore").write_text("secret/\n", encoding="utf-8")
        (self.root / "secret").mkdir()
        (self.root / "secret" / "s.py").write_text("baz = 3\n", encoding="utf-8")
        result = navigate.find("baz", str(self.root))
        self.assertIn("a.py:7:", result)
        self.assertNotIn("secret", result)
        self.assertNotIn("node_modules", result)

    def test_outline_python_decorator_starts_range(self):
        (self.root / "d.py").write_text("@staticmethod\ndef f():\n    return 1\n", encoding="utf-8")
        self.assertIn("1-3 def f", navigate.outline(str(self.root / "d.py")))

    def test_outline_js_forms(self):
        (self.root / "m.js").write_text(
            "export default function main() {}\n"
            "const load = async (x) => x;\n"
            "const one = x => x;\n"
            "export class Store {}\n"
            "const value = 3;\n",
            encoding="utf-8",
        )
        result = navigate.outline(str(self.root / "m.js"))
        for n in ("1 export default", "2 const load", "3 const one", "4 export class"):
            self.assertIn(n, result)
        self.assertNotIn("5 const value", result)

    def test_outline_shell_ignores_comments(self):
        (self.root / "s.sh").write_text("# just a comment\nbuild() {\n  echo hi\n}\nfunction clean {\n}\n", encoding="utf-8")
        result = navigate.outline(str(self.root / "s.sh"))
        self.assertNotIn("comment", result)
        self.assertIn("2 build()", result)
        self.assertIn("5 function clean", result)
        (self.root / "p.ps1").write_text("# comment\nfunction Get-Thing {\n}\n", encoding="utf-8")
        ps = navigate.outline(str(self.root / "p.ps1"))
        self.assertNotIn("comment", ps)
        self.assertIn("2 function Get-Thing", ps)

    def test_outline_markdown_skips_code_fences(self):
        (self.root / "f.md").write_text("# Real\n```bash\n# not a heading\n```\n## Also real\n", encoding="utf-8")
        result = navigate.outline(str(self.root / "f.md"))
        self.assertIn("1 # Real", result)
        self.assertIn("5 ## Also real", result)
        self.assertNotIn("not a heading", result)

    def test_find_any_text_extension_skips_binary(self):
        (self.root / "main.go").write_text("func baz() {}\n", encoding="utf-8")
        (self.root / "Makefile").write_text("baz:\n", encoding="utf-8")
        (self.root / "blob.bin").write_bytes(b"baz\0\x01\x02")
        result = navigate.find("baz", str(self.root))
        self.assertIn("main.go:1:", result)
        self.assertIn("Makefile:1:", result)
        self.assertNotIn("blob.bin", result)

    def test_find_context_merges_close_hits(self):
        (self.root / "m.py").write_text("x = 1\nhit\nhit\ny = 2\n\n\n\nhit\n", encoding="utf-8")
        result = navigate.find("hit", str(self.root), glob="m.py", context=1)
        self.assertEqual(result.count("m.py:3"), 1)
        self.assertEqual(result.count("--"), 1)

    def test_outline_line_count(self):
        self.assertIn("a.py (8 lines)", navigate.outline(str(self.root / "a.py")))

    def test_outline_python_defs_in_blocks(self):
        (self.root / "b.py").write_text(
            "try:\n    import x\nexcept ImportError:\n    def x():\n        pass\n"
            "if True:\n    class C:\n        def m(self):\n            pass\n",
            encoding="utf-8",
        )
        result = navigate.outline(str(self.root / "b.py"))
        self.assertIn("\n4-5 def x", result)
        self.assertIn("\n7-9 class C", result)
        self.assertIn("\n  8-9 def m", result)

    def test_outline_other_languages(self):
        cases = {
            "g.go": ("type Store struct {\n}\nfunc (s *Store) Get() {}\nvar x = 1\n", ["1 type", "3 func"]),
            "r.rs": ("pub struct S;\nimpl S {\n    pub async fn run() {}\n}\nconst N: u8 = 1;\n", ["1 pub struct", "2 impl", "3 pub async fn"]),
            "j.java": ("public class A {\n    public static void main(String[] a) {\n    private int x = f();\n}\n", ["1 public class", "2 public static void"]),
            "k.kt": ("data class P(val x: Int)\nfun main() {}\n", ["1 data class", "2 fun main"]),
            "r.rb": ("module M\n  def run\n  end\nend\n", ["1 module", "2 def run"]),
            "p.php": ("<?php\nfinal class A {\n    public static function make() {}\n}\n", ["2 final class", "3 public static function"]),
        }
        for name, (src, expected) in cases.items():
            (self.root / name).write_text(src, encoding="utf-8")
            result = navigate.outline(str(self.root / name))
            for row in expected:
                self.assertIn(row, result, name)
        self.assertNotIn("4 var", navigate.outline(str(self.root / "g.go")))
        self.assertNotIn("5 const", navigate.outline(str(self.root / "r.rs")))
        self.assertNotIn("3 private", navigate.outline(str(self.root / "j.java")))

    def test_outline_unsupported_extension(self):
        (self.root / "x.c").write_text("int main() {}\n", encoding="utf-8")
        self.assertIn("outline not supported for .c", navigate.outline(str(self.root / "x.c")))


if __name__ == "__main__":
    unittest.main()
