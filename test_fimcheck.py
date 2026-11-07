import os
import tempfile
import unittest

import fimcheck


def write(root, rel, text):
    p = os.path.join(root, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as fh:
        fh.write(text)
    return p


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        write(self.root, "a.txt", "alpha")
        write(self.root, "sub/b.txt", "beta")

    def tearDown(self):
        self.tmp.cleanup()

    def test_snapshot_lists_files(self):
        self.assertEqual(set(fimcheck.snapshot(self.root)), {"a.txt", "sub/b.txt"})

    def test_hash_known_value(self):
        snap = fimcheck.snapshot(self.root)
        self.assertEqual(snap["a.txt"]["sha256"],
                         "8ed3f6ad685b959ead7022518e1af76cd816f8e8ec7ccdda1ed4018e8f2223f8")

    def test_exclude(self):
        self.assertEqual(set(fimcheck.snapshot(self.root, ["sub"])), {"a.txt"})
        self.assertEqual(set(fimcheck.snapshot(self.root, ["*.txt"])), set())

    def test_symlink_skipped(self):
        os.symlink(os.path.join(self.root, "a.txt"), os.path.join(self.root, "link"))
        self.assertNotIn("link", fimcheck.snapshot(self.root))

    def test_diff(self):
        old = fimcheck.snapshot(self.root)
        write(self.root, "a.txt", "changed")
        os.remove(os.path.join(self.root, "sub/b.txt"))
        write(self.root, "c.txt", "new")
        os.chmod(os.path.join(self.root, "c.txt"), 0o600)
        d = fimcheck.diff(old, fimcheck.snapshot(self.root))
        self.assertEqual(d["modified"], ["a.txt"])
        self.assertEqual(d["removed"], ["sub/b.txt"])
        self.assertEqual(d["added"], ["c.txt"])
        self.assertTrue(fimcheck.has_changes(d))

    def test_mode_change(self):
        old = fimcheck.snapshot(self.root)
        os.chmod(os.path.join(self.root, "a.txt"), 0o600)
        d = fimcheck.diff(old, fimcheck.snapshot(self.root))
        self.assertEqual(d["mode_changed"], ["a.txt"])

    def test_cli_roundtrip(self):
        base = os.path.join(self.root, "base.json")
        self.assertEqual(fimcheck.main(["init", self.root, "-b", base]), 0)
        self.assertEqual(fimcheck.main(["check", self.root, "-b", base]), 0)
        write(self.root, "a.txt", "tampered")
        self.assertEqual(fimcheck.main(["check", self.root, "-b", base]), 1)

    def test_missing_baseline(self):
        self.assertEqual(fimcheck.main(["check", self.root, "-b", "/nonexistent/x.json"]), 2)


if __name__ == "__main__":
    unittest.main()
