import datetime as dt

from mdconv import tables


def test_parse_tables_with_titles_escapes_and_code_blocks():
    md = """# Doc

## Umsatz

| Monat | Notiz |
|:---|---:|
| Jan | a \\| b |
| Feb |

```
| keine | tabelle |
|---|---|
```

Freitext | mit Pipe
"""
    found = tables.parse_tables(md)
    assert len(found) == 1
    assert found[0].title == "Umsatz"
    assert found[0].rows == [["Monat", "Notiz"], ["Jan", "a | b"], ["Feb", ""]]


def test_table_without_heading_gets_numbered_title():
    found = tables.parse_tables("a | b\n---|---\n1 | 2\n")
    assert found[0].title == "Tabelle 1"
    assert found[0].rows == [["a", "b"], ["1", "2"]]


def test_to_markdown_escapes_and_pads():
    md = tables.to_markdown([["h1", "h2"], ["x|y"], [3.0, dt.datetime(2026, 1, 2)]])
    assert md.splitlines() == [
        "| h1 | h2 |",
        "|---|---|",
        "| x\\|y |  |",
        "| 3 | 2026-01-02 |",
    ]


def test_trim_removes_empty_trailing_rows_and_columns():
    rows = [["a", "b", None], ["1", "", None], [None, None, None]]
    assert tables.trim(rows) == [["a", "b"], ["1", ""]]
