import contextlib
import io
import json
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


def run_main(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = fimcheck.main(list(argv))
    return code, out.getvalue(), err.getvalue()


class NewFeatureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = os.path.join(self.tmp.name, "tree")
        os.makedirs(self.root)
        write(self.root, "a.txt", "alpha")
        write(self.root, "b.txt", "beta")
        self.base = os.path.join(self.tmp.name, "base.json")
        run_main("init", self.root, "-b", self.base)

    def tearDown(self):
        self.tmp.cleanup()

    def test_snapshot_records_owner(self):
        snap = fimcheck.snapshot(self.root)
        self.assertEqual(snap["a.txt"]["uid"], os.stat(os.path.join(self.root, "a.txt")).st_uid)

    def test_owner_change_detected_when_both_sides_have_owner(self):
        old = fimcheck.snapshot(self.root)
        new = json.loads(json.dumps(old))
        new["a.txt"]["uid"] = old["a.txt"]["uid"] + 1
        d = fimcheck.diff(old, new)
        self.assertEqual(d["owner_changed"], ["a.txt"])
        self.assertTrue(fimcheck.has_changes(d))

    def test_old_baselines_without_owner_do_not_false_alarm(self):
        old = {p: {"sha256": v["sha256"], "mode": v["mode"]} for p, v in fimcheck.snapshot(self.root).items()}
        self.assertFalse(fimcheck.has_changes(fimcheck.diff(old, fimcheck.snapshot(self.root))))

    def test_mode_and_owner_reported_independently(self):
        old = fimcheck.snapshot(self.root)
        new = json.loads(json.dumps(old))
        new["a.txt"]["uid"] += 1
        new["a.txt"]["mode"] ^= 0o001
        d = fimcheck.diff(old, new)
        self.assertEqual((d["mode_changed"], d["owner_changed"]), (["a.txt"], ["a.txt"]))

    def test_content_change_takes_precedence(self):
        old = fimcheck.snapshot(self.root)
        new = json.loads(json.dumps(old))
        new["a.txt"]["sha256"] = "0" * 64
        new["a.txt"]["uid"] += 1
        d = fimcheck.diff(old, new)
        self.assertEqual((d["modified"], d["owner_changed"]), (["a.txt"], []))

    def test_check_json(self):
        write(self.root, "a.txt", "tampered")
        code, out, _ = run_main("check", self.root, "-b", self.base, "--json")
        data = json.loads(out)
        self.assertEqual(code, 1)
        self.assertFalse(data["ok"])
        self.assertEqual(data["changes"]["modified"], ["a.txt"])

    def test_check_json_clean(self):
        code, out, _ = run_main("check", self.root, "-b", self.base, "--json")
        self.assertEqual((code, json.loads(out)["ok"]), (0, True))

    def test_update_accepts_changes_and_prints_them(self):
        write(self.root, "a.txt", "tampered")
        write(self.root, "new.txt", "x")
        code, out, err = run_main("update", self.root, "-b", self.base)
        self.assertEqual(code, 0)
        self.assertIn("MODIFIED      a.txt", out)
        self.assertIn("ADDED         new.txt", out)
        self.assertIn("2 change(s) accepted", err)
        self.assertEqual(run_main("check", self.root, "-b", self.base)[0], 0)

    def test_update_needs_an_existing_baseline(self):
        code, _, err = run_main("update", self.root, "-b", os.path.join(self.tmp.name, "nope.json"))
        self.assertEqual(code, 2)
        self.assertIn("cannot read baseline", err)

    def test_baseline_written_atomically_and_versioned(self):
        with open(self.base) as fh:
            data = json.load(fh)
        self.assertEqual(data["version"], 2)
        self.assertFalse(os.path.exists(self.base + ".tmp"))

    def test_text_output_labels(self):
        os.remove(os.path.join(self.root, "b.txt"))
        _, out, _ = run_main("check", self.root, "-b", self.base)
        self.assertIn("REMOVED       b.txt", out)


if __name__ == "__main__":
    unittest.main()
