"""Markdown, HTML, and plain-text rendering for daily reports."""

from __future__ import annotations

import html
import re


EMAIL_STYLES = {
    "body": (
        "margin:0;padding:0;background:#f6f8fb;color:#1f2937;"
        "font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','Noto Sans TC','Microsoft JhengHei',Arial,sans-serif;"
        "line-height:1.55;"
    ),
    "content": "max-width:1180px;margin:0 auto;padding:24px;",
    "h1": "font-size:26px;line-height:1.25;margin:0 0 18px;color:#111827;font-weight:700;",
    "h2": "font-size:20px;margin:28px 0 12px;color:#111827;border-bottom:2px solid #d8dee9;padding-bottom:6px;font-weight:700;",
    "h3": "font-size:16px;margin:20px 0 10px;color:#111827;font-weight:700;",
    "h4": "font-size:15px;margin:16px 0 8px;color:#111827;font-weight:700;",
    "p": "margin:8px 0 12px;",
    "ul": "margin:8px 0 14px;padding-left:22px;",
    "li": "margin:4px 0;",
    "table_wrap": "margin:12px 0 22px;background:#ffffff;max-width:100%;",
    "table": (
        "border-collapse:collapse;width:100%;max-width:100%;table-layout:fixed;"
        "font-size:13px;border:1px solid #9ca3af;"
    ),
    "th": (
        "border:1px solid #9ca3af;padding:8px 10px;text-align:left;vertical-align:top;"
        "background:#eef2f7;color:#111827;font-weight:700;white-space:normal;"
        "word-break:break-word;overflow-wrap:anywhere;"
    ),
    "td": (
        "border:1px solid #9ca3af;padding:8px 10px;text-align:left;vertical-align:top;"
        "background:#ffffff;color:#1f2937;white-space:normal;word-break:break-word;overflow-wrap:anywhere;"
    ),
    "code": "background:#eef2f7;border-radius:4px;padding:1px 4px;font-family:Consolas,'Courier New',monospace;",
    "a": "color:#2563eb;text-decoration:none;",
}


def split_markdown_table_row(line: str) -> list[str]:
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    return [cell.strip() for cell in stripped.split("|")]


def is_markdown_table_separator(line: str) -> bool:
    cells = split_markdown_table_row(line)
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell.strip()) is not None for cell in cells)


def inline_markdown_to_html(text: str) -> str:
    placeholders: list[str] = []

    def hold(value: str) -> str:
        placeholders.append(value)
        return f"\u0000{len(placeholders) - 1}\u0000"

    def replace_link(match: re.Match[str]) -> str:
        label = html.escape(match.group(1), quote=False)
        url = html.escape(match.group(2), quote=True)
        return hold(
            f'<a href="{url}" target="_blank" rel="noopener noreferrer" style="{EMAIL_STYLES["a"]}">{label}</a>'
        )

    def replace_code(match: re.Match[str]) -> str:
        escaped = html.escape(match.group(1), quote=False)
        return hold(f'<code style="{EMAIL_STYLES["code"]}">{escaped}</code>')

    working = re.sub(r"`([^`]+)`", replace_code, text)
    working = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", replace_link, working)
    working = html.escape(working, quote=False)
    working = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", working)
    for index, value in enumerate(placeholders):
        working = working.replace(f"\u0000{index}\u0000", value)
    return working


def markdown_to_email_html(markdown_text: str, *, title: str = "每日盤後 AI 交易策略報告") -> str:
    lines = markdown_text.splitlines()
    body: list[str] = []
    paragraph: list[str] = []
    in_list = False

    def flush_paragraph() -> None:
        nonlocal paragraph
        if paragraph:
            text = " ".join(part.strip() for part in paragraph if part.strip())
            body.append(f'<p style="{EMAIL_STYLES["p"]}">{inline_markdown_to_html(text)}</p>')
            paragraph = []

    def close_list() -> None:
        nonlocal in_list
        if in_list:
            body.append("</ul>")
            in_list = False

    i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        if not stripped:
            flush_paragraph()
            close_list()
            i += 1
            continue
        if stripped.startswith("|"):
            flush_paragraph()
            close_list()
            table_lines: list[str] = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                table_lines.append(lines[i])
                i += 1
            if len(table_lines) >= 2 and is_markdown_table_separator(table_lines[1]):
                headers = split_markdown_table_row(table_lines[0])
                rows = [split_markdown_table_row(row) for row in table_lines[2:]]
                body.append(f'<div style="{EMAIL_STYLES["table_wrap"]}"><table style="{EMAIL_STYLES["table"]}">')
                body.append(
                    "<thead><tr>"
                    + "".join(
                        f'<th style="{EMAIL_STYLES["th"]}">{inline_markdown_to_html(header)}</th>'
                        for header in headers
                    )
                    + "</tr></thead>"
                )
                body.append("<tbody>")
                for row in rows:
                    padded = row + [""] * max(0, len(headers) - len(row))
                    body.append(
                        "<tr>"
                        + "".join(
                            f'<td style="{EMAIL_STYLES["td"]}">{inline_markdown_to_html(cell)}</td>'
                            for cell in padded[: len(headers)]
                        )
                        + "</tr>"
                    )
                body.append("</tbody></table></div>")
            else:
                body.extend(
                    f'<p style="{EMAIL_STYLES["p"]}">{inline_markdown_to_html(line)}</p>'
                    for line in table_lines
                )
            continue

        heading_match = re.match(r"^(#{1,4})\s+(.+)$", stripped)
        if heading_match:
            flush_paragraph()
            close_list()
            level = min(len(heading_match.group(1)), 4)
            body.append(
                f'<h{level} style="{EMAIL_STYLES[f"h{level}"]}">'
                f"{inline_markdown_to_html(heading_match.group(2))}</h{level}>"
            )
            i += 1
            continue
        if stripped.startswith("- "):
            flush_paragraph()
            if not in_list:
                body.append(f'<ul style="{EMAIL_STYLES["ul"]}">')
                in_list = True
            body.append(f'<li style="{EMAIL_STYLES["li"]}">{inline_markdown_to_html(stripped[2:])}</li>')
            i += 1
            continue
        close_list()
        paragraph.append(stripped)
        i += 1

    flush_paragraph()
    close_list()
    escaped_title = html.escape(title, quote=False)
    return (
        "<!doctype html>\n"
        '<html lang="zh-Hant">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        f"<title>{escaped_title}</title>\n"
        "</head>\n"
        f'<body style="{EMAIL_STYLES["body"]}">\n'
        f'<div style="{EMAIL_STYLES["content"]}">\n'
        + "\n".join(body)
        + "\n</div>\n"
        "</body>\n"
        "</html>\n"
    )


def markdown_to_plain_text(markdown_text: str) -> str:
    lines: list[str] = []
    for raw_line in markdown_text.splitlines():
        line = raw_line.strip()
        if not line:
            lines.append("")
        elif is_markdown_table_separator(line):
            continue
        elif line.startswith("|"):
            lines.append("  " + " | ".join(split_markdown_table_row(line)))
        else:
            heading_match = re.match(r"^(#{1,4})\s+(.+)$", line)
            if heading_match:
                heading = heading_match.group(2)
                lines.extend((heading, "-" * min(40, len(heading))))
                continue
            line = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1: \2", line)
            lines.append(line.replace("**", "").replace("`", ""))
    return "\n".join(lines).strip() + "\n"
