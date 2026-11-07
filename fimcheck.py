#!/usr/bin/env python3
"""fimcheck - simple file integrity monitor.

Record a SHA-256 baseline of a directory, then later report files that were
added, removed, modified, or had their permissions changed.
Standard library only. Exit code 0 = no changes, 1 = changes, 2 = error.
"""
import argparse
import fnmatch
import hashlib
import json
import os
import stat
import sys

__version__ = "1.0.0"


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def excluded(rel, patterns):
    parts = rel.split("/")
    return any(fnmatch.fnmatch(rel, p) or any(fnmatch.fnmatch(x, p) for x in parts)
               for p in patterns)


def snapshot(root, exclude=()):
    """Return {relative_path: {sha256, mode}} for regular files under root.

    Symlinks are not followed and are not recorded.
    """
    snap = {}
    for dirpath, dirs, files in os.walk(root, followlinks=False):
        rel_dir = os.path.relpath(dirpath, root)
        dirs[:] = sorted(d for d in dirs
                         if not excluded(os.path.normpath(os.path.join(rel_dir, d)).replace(os.sep, "/"), exclude))
        for name in sorted(files):
            full = os.path.join(dirpath, name)
            rel = os.path.normpath(os.path.join(rel_dir, name)).replace(os.sep, "/")
            if excluded(rel, exclude) or os.path.islink(full):
                continue
            try:
                st = os.stat(full)
                if not stat.S_ISREG(st.st_mode):
                    continue
                snap[rel] = {"sha256": sha256_file(full), "mode": stat.S_IMODE(st.st_mode)}
            except OSError:
                continue
    return snap


def diff(old, new):
    """Compare two snapshots; return dict of sorted lists."""
    added = sorted(set(new) - set(old))
    removed = sorted(set(old) - set(new))
    modified, mode_changed = [], []
    for p in sorted(set(old) & set(new)):
        if old[p]["sha256"] != new[p]["sha256"]:
            modified.append(p)
        elif old[p]["mode"] != new[p]["mode"]:
            mode_changed.append(p)
    return {"added": added, "removed": removed, "modified": modified,
            "mode_changed": mode_changed}


def has_changes(d):
    return any(d.values())


def main(argv=None):
    ap = argparse.ArgumentParser(description="File integrity monitor (SHA-256 baseline).")
    ap.add_argument("--version", action="version", version=__version__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, helptext in (("init", "create a baseline"), ("check", "compare against a baseline")):
        sp = sub.add_parser(name, help=helptext)
        sp.add_argument("directory")
        sp.add_argument("-b", "--baseline", default="fim-baseline.json")
        sp.add_argument("-x", "--exclude", action="append", default=[],
                        help="glob pattern to skip (repeatable)")
    args = ap.parse_args(argv)

    if not os.path.isdir(args.directory):
        print("fimcheck: not a directory: %s" % args.directory, file=sys.stderr)
        return 2
    base_abs = os.path.abspath(args.baseline)
    exclude = list(args.exclude)
    if os.path.dirname(base_abs) == os.path.abspath(args.directory):
        exclude.append(os.path.basename(base_abs))
    snap = snapshot(args.directory, exclude)

    if args.cmd == "init":
        with open(args.baseline, "w") as fh:
            json.dump({"version": 1, "files": snap}, fh, indent=2, sort_keys=True)
        print("fimcheck: baseline of %d file(s) written to %s" % (len(snap), args.baseline))
        return 0

    try:
        with open(args.baseline) as fh:
            old = json.load(fh)["files"]
    except (OSError, ValueError, KeyError) as exc:
        print("fimcheck: cannot read baseline: %s" % exc, file=sys.stderr)
        return 2
    d = diff(old, snap)
    for label in ("added", "removed", "modified", "mode_changed"):
        for p in d[label]:
            print("%-12s %s" % (label.upper(), p))
    print("fimcheck: %s" % ("changes detected" if has_changes(d) else "no changes"),
          file=sys.stderr)
    return 1 if has_changes(d) else 0


if __name__ == "__main__":
    sys.exit(main())
