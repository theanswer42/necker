"""Typed CLI output writer.

The CLI separates three concerns on its output streams:
  - logs (via `logger`, stderr): progress and status lines
  - data output (via `OutputWriter`, stdout): structured results
  - interaction (via `print`/`input`, stdout): prompts

`OutputWriter` takes a `Renderer` and exposes three methods over typed
dataclass instances: `record()`, `collection()`, and `section()`.

Field-level rendering hints come from dataclass metadata:
  - `cli_format`: "cents_to_dollars" | "iso_date"
  - `cli_label`: override the displayed field name
"""

from __future__ import annotations

import sys
from dataclasses import fields, is_dataclass
from datetime import date, datetime
from typing import Any, Protocol, TextIO

from logger import get_logger

_logger = get_logger()
_warned_formats: set[str] = set()


def _format_value(value: Any, fmt: str | None) -> str:
    if value is None:
        return ""
    if fmt == "cents_to_dollars":
        return f"${value / 100:,.2f}"
    if fmt == "iso_date":
        if isinstance(value, (date, datetime)):
            return value.isoformat()
        return str(value)
    if fmt is not None and fmt not in _warned_formats:
        _warned_formats.add(fmt)
        _logger.warning(f"Unknown cli_format '{fmt}'; falling back to str()")
    return str(value)


def _is_dataclass_instance(obj: Any) -> bool:
    return is_dataclass(obj) and not isinstance(obj, type)


class Renderer(Protocol):
    def render_record(self, obj: Any) -> None: ...
    def render_collection(self, items: list, *, title: str | None = None) -> None: ...
    def render_section(self, title: str, obj: Any) -> None: ...


class TextRenderer:
    """Render dataclass-shaped output as human-readable text."""

    def __init__(self, stream: TextIO | None = None):
        self._stream = stream if stream is not None else sys.stdout

    def _write(self, text: str = "") -> None:
        print(text, file=self._stream)

    def render_record(self, obj: Any) -> None:
        for line in self._record_lines(obj):
            self._write(line)

    def render_collection(self, items: list, *, title: str | None = None) -> None:
        if not items:
            return
        if title:
            self._write()
            self._write(f"{title}:")
            self._write("=" * 80)
        for line in self._table_lines(items):
            self._write(line)

    def render_section(self, title: str, obj: Any) -> None:
        self._write()
        self._write(title)
        self._write("=" * 80)
        if obj is None:
            return
        if isinstance(obj, list):
            for line in self._table_lines(obj):
                self._write(line)
            return
        if _is_dataclass_instance(obj):
            for line in self._record_lines(obj):
                self._write(line)
            return
        self._write(str(obj))

    def _record_lines(self, obj: Any, indent: int = 0) -> list[str]:
        if not _is_dataclass_instance(obj):
            return [("  " * indent) + str(obj)]

        prefix = "  " * indent
        lines: list[str] = []
        for f in fields(obj):
            label = f.metadata.get("cli_label", f.name)
            value = getattr(obj, f.name)
            fmt = f.metadata.get("cli_format")

            if _is_dataclass_instance(value):
                lines.append(f"{prefix}{label}:")
                lines.extend(self._record_lines(value, indent + 1))
            elif isinstance(value, list) and value and _is_dataclass_instance(value[0]):
                lines.append(f"{prefix}{label}:")
                lines.extend(self._table_lines(value, indent=indent + 1))
            elif isinstance(value, dict):
                lines.append(f"{prefix}{label}:")
                for k, v in value.items():
                    lines.append(f"{prefix}  {k}: {_format_value(v, fmt)}")
            else:
                lines.append(f"{prefix}{label}: {_format_value(value, fmt)}")
        return lines

    def _table_lines(self, items: list, indent: int = 0) -> list[str]:
        if not items:
            return []
        if not _is_dataclass_instance(items[0]):
            prefix = "  " * indent
            return [f"{prefix}{item}" for item in items]

        item_cls = type(items[0])
        cols = [(f.metadata.get("cli_label", f.name), f) for f in fields(item_cls)]

        rendered: list[list[str]] = []
        for item in items:
            row = []
            for _, f in cols:
                value = getattr(item, f.name)
                row.append(_format_value(value, f.metadata.get("cli_format")))
            rendered.append(row)

        widths = [len(label) for label, _ in cols]
        for row in rendered:
            for i, cell in enumerate(row):
                widths[i] = max(widths[i], len(cell))

        prefix = "  " * indent
        sep = "  "
        lines: list[str] = []
        lines.append(
            prefix
            + sep.join(label.ljust(widths[i]) for i, (label, _) in enumerate(cols))
        )
        lines.append(prefix + "-" * (sum(widths) + len(sep) * (len(cols) - 1)))
        for row in rendered:
            lines.append(
                prefix + sep.join(cell.ljust(widths[i]) for i, cell in enumerate(row))
            )
        return lines


class OutputWriter:
    """Emit typed CLI data through a renderer."""

    def __init__(self, renderer: Renderer):
        self._renderer = renderer

    def record(self, obj: Any) -> None:
        """Emit a single dataclass instance as a key-value record."""
        self._renderer.render_record(obj)

    def collection(self, items: list, *, title: str | None = None) -> None:
        """Emit a list of dataclass instances as a table."""
        self._renderer.render_collection(items, title=title)

    def section(self, title: str, obj: Any) -> None:
        """Emit a titled block with a dataclass, list, or scalar body."""
        self._renderer.render_section(title, obj)
