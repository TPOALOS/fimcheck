# fimcheck

A tiny file integrity monitor. Record a SHA-256 baseline of a directory, then later
see which files were added, removed, modified, or had their permissions changed.
Standard library only; read-only on the monitored directory.

## Usage

```bash
python3 fimcheck.py init /etc/myapp -b baseline.json
python3 fimcheck.py check /etc/myapp -b baseline.json
python3 fimcheck.py check /srv/site -b baseline.json -x node_modules -x "*.log"
python3 fimcheck.py check /etc/myapp -b baseline.json --json      # machine-readable
python3 fimcheck.py update /etc/myapp -b baseline.json            # after you reviewed the changes
# or: pip install git+https://github.com/TPOALOS/fimcheck && fimcheck check ...
```

Output lines look like `MODIFIED  conf/app.ini`; the labels are `ADDED`, `REMOVED`, `MODIFIED`, `MODE_CHANGED` and
`OWNER_CHANGED` (uid/gid, recorded since 1.1; baselines from 1.0 are still readable and never raise owner alarms).
`update` prints what changed and then accepts the current state as the new baseline, so a legitimate change
does not keep alerting. Baselines are written atomically.

Exit codes: `0` no changes,
`1` changes detected, `2` error (bad directory or unreadable baseline).

Notes:
- Symlinks are not followed or recorded.
- A baseline stored inside the monitored directory is excluded automatically.
- Keep the baseline somewhere an attacker cannot rewrite it (read-only media, another host).

## Tests

```bash
python3 -m unittest -v
```

## License

MIT (c) TPOALOS

---

**More tools by [TPOALOS](https://github.com/TPOALOS):** [permaudit](https://github.com/TPOALOS/permaudit) · [headercheck](https://github.com/TPOALOS/headercheck) · [jwtlint](https://github.com/TPOALOS/jwtlint) · [all 51 tools](https://tpoalos.github.io)
