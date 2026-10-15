import os
from pathlib import Path
import unittest
from unittest.mock import patch

from gene_literature_gui import user_cache_dir, validate_search


class GUIOptionTests(unittest.TestCase):
    def test_valid_options(self):
        self.assertEqual(validate_search(" p53 ", "30", "인용순"), ("p53", 30, "cited"))

    def test_invalid_options(self):
        for gene, count, sort in [("", "30", "최신순"), ("FASN", "no", "최신순"),
                                  ("FASN", "0", "최신순"), ("FASN", "301", "최신순"),
                                  ("FASN", "30", "unknown")]:
            with self.subTest(gene=gene, count=count, sort=sort), self.assertRaises(ValueError):
                validate_search(gene, count, sort)

    def test_writable_platform_cache_paths(self):
        with patch("gene_literature_gui.sys.platform", "win32"), patch.dict(os.environ, {"LOCALAPPDATA": "/example/local"}):
            self.assertEqual(user_cache_dir(), Path("/example/local/OpenGeneLiterature"))
        with patch("gene_literature_gui.sys.platform", "darwin"):
            self.assertEqual(user_cache_dir(), Path.home() / "Library/Caches/OpenGeneLiterature")


if __name__ == "__main__":
    unittest.main()
