# API Reference

Auto-generated from docstrings via [mkdocstrings].

## Modern API

::: rglob.rglob.find
    options:
      show_root_heading: true
      show_source: false

::: rglob.rglob.find_all
    options:
      show_root_heading: true
      show_source: false

## Legacy API (still supported)

::: rglob.rglob.rglob
    options:
      show_root_heading: true
      show_source: false

::: rglob.rglob.rglob_
    options:
      show_root_heading: true
      show_source: false

::: rglob.rglob.lcount
    options:
      show_root_heading: true
      show_source: false

::: rglob.rglob.tsize
    options:
      show_root_heading: true
      show_source: false

## Unit helpers

::: rglob.rglob.kilobytes
    options:
      show_root_heading: true
      show_source: false

::: rglob.rglob.megabytes
    options:
      show_root_heading: true
      show_source: false

::: rglob.rglob.gigabytes
    options:
      show_root_heading: true
      show_source: false

::: rglob.rglob.terabytes
    options:
      show_root_heading: true
      show_source: false

!!! note "Path return at 2.0"
    As of 2.0, `rglob()` / `rglob_()` return `list[Path]` (previously
    `list[str]`). See [migrating to 2.0](migrating-to-2.0.md) for the
    one-line migration. The new `find()` / `find_all()` family already
    returns `Path` so code targeting the modern API doesn't need to change.

[mkdocstrings]: https://mkdocstrings.github.io/
