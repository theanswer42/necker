"""Tests for the CLI OutputWriter / TextRenderer."""

import io
from dataclasses import dataclass, field
from datetime import date

from cli.output import OutputWriter, TextRenderer


def _writer() -> tuple[OutputWriter, io.StringIO]:
    buf = io.StringIO()
    return OutputWriter(TextRenderer(stream=buf)), buf


@dataclass
class _Simple:
    name: str
    count: int


@dataclass
class _Money:
    name: str
    amount: int = field(metadata={"cli_format": "cents_to_dollars"})


@dataclass
class _Dated:
    when: date = field(metadata={"cli_format": "iso_date"})
    note: str = ""


@dataclass
class _Labeled:
    category_name: str = field(metadata={"cli_label": "Category"})
    amount: int = field(
        default=0, metadata={"cli_label": "Total", "cli_format": "cents_to_dollars"}
    )


@dataclass
class _Nested:
    id: int
    inner: _Simple


class TestRenderRecord:
    def test_simple_dataclass_emits_key_value_lines(self):
        w, buf = _writer()
        w.record(_Simple(name="foo", count=3))
        assert buf.getvalue() == "name: foo\ncount: 3\n"

    def test_cents_to_dollars_formatter(self):
        w, buf = _writer()
        w.record(_Money(name="rent", amount=123456))
        assert "amount: $1,234.56" in buf.getvalue()

    def test_iso_date_formatter(self):
        w, buf = _writer()
        w.record(_Dated(when=date(2025, 10, 15)))
        assert "when: 2025-10-15" in buf.getvalue()

    def test_cli_label_overrides_field_name(self):
        w, buf = _writer()
        w.record(_Labeled(category_name="Groceries", amount=500))
        output = buf.getvalue()
        assert "Category: Groceries" in output
        assert "Total: $5.00" in output
        # Original field name should not appear as a label
        assert "category_name:" not in output

    def test_none_values_render_as_empty_string(self):
        w, buf = _writer()
        w.record(_Dated(when=None, note="hi"))
        assert "when: \n" in buf.getvalue()

    def test_nested_dataclass_renders_recursively(self):
        w, buf = _writer()
        w.record(_Nested(id=1, inner=_Simple(name="x", count=5)))
        output = buf.getvalue()
        assert "id: 1" in output
        assert "inner:" in output
        assert "  name: x" in output
        assert "  count: 5" in output


class TestRenderCollection:
    def test_empty_collection_emits_nothing(self):
        w, buf = _writer()
        w.collection([])
        assert buf.getvalue() == ""

    def test_collection_emits_aligned_table_with_headers(self):
        w, buf = _writer()
        w.collection([_Simple(name="a", count=1), _Simple(name="bbb", count=22)])
        output = buf.getvalue()
        lines = [line for line in output.splitlines() if line]
        # Header row contains field names
        assert "name" in lines[0]
        assert "count" in lines[0]
        # Separator line
        assert set(lines[1]) == {"-"}
        # Data rows present
        assert "a" in lines[2]
        assert "bbb" in lines[3]

    def test_collection_uses_cli_label_for_headers(self):
        w, buf = _writer()
        w.collection([_Labeled(category_name="Food", amount=100)])
        output = buf.getvalue()
        assert "Category" in output
        assert "Total" in output
        assert "category_name" not in output

    def test_collection_formats_cells_via_cli_format(self):
        w, buf = _writer()
        w.collection([_Money(name="rent", amount=123456)])
        assert "$1,234.56" in buf.getvalue()

    def test_collection_with_title_emits_title_header(self):
        w, buf = _writer()
        w.collection([_Simple(name="x", count=1)], title="Items")
        output = buf.getvalue()
        assert "Items:" in output
        assert "=" * 80 in output


class TestRenderSection:
    def test_section_renders_title_then_dataclass(self):
        w, buf = _writer()
        w.section("Report", _Simple(name="hi", count=2))
        output = buf.getvalue()
        assert "Report" in output
        assert "=" * 80 in output
        assert "name: hi" in output
        assert "count: 2" in output

    def test_section_renders_list_as_table(self):
        w, buf = _writer()
        w.section("Items", [_Simple(name="a", count=1)])
        output = buf.getvalue()
        assert "Items" in output
        assert "name" in output
        assert "count" in output


class TestUnknownFormat:
    def test_unknown_format_falls_back_to_str(self):
        @dataclass
        class Weird:
            x: int = field(metadata={"cli_format": "does-not-exist"})

        w, buf = _writer()
        w.record(Weird(x=42))
        assert "x: 42" in buf.getvalue()


class TestDictValueFormatting:
    def test_dict_field_applies_cli_format_to_values(self):
        @dataclass
        class WithDict:
            name: str
            breakdown: dict = field(
                default_factory=dict, metadata={"cli_format": "cents_to_dollars"}
            )

        w, buf = _writer()
        w.record(WithDict(name="x", breakdown={1: 10050, 2: 25000}))
        output = buf.getvalue()
        assert "breakdown:" in output
        assert "1: $100.50" in output
        assert "2: $250.00" in output
