# fimcheck

A tiny file integrity monitor. Record a SHA-256 baseline of a directory, then later
see which files were added, removed, modified, or had their permissions changed.
Standard library only; read-only on the monitored directory.

## Usage

```bash
python3 fimcheck.py init /etc/myapp -b baseline.json
python3 fimcheck.py check /etc/myapp -b baseline.json
python3 fimcheck.py check /srv/site -b baseline.json -x node_modules -x "*.log"
```

Output lines look like `MODIFIED  conf/app.ini`. Exit codes: `0` no changes,
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
