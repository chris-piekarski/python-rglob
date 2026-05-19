# Security Policy

## Reporting a vulnerability

`rglob` is a small filesystem-walking helper and not part of any critical
security boundary, but if you spot something that could harm users (e.g. a
path-traversal flaw, symlink-escape, or arbitrary file disclosure), please
report it privately rather than via a public issue.

Open a [private security advisory on GitHub](https://github.com/chris-piekarski/python-rglob/security/advisories/new).

You can expect an acknowledgement within a week. Fix timing depends on
severity and complexity.

## Supported versions

Only the latest minor release on PyPI is supported. Older versions may
contain known issues that are fixed only in the current line.
