import os
import subprocess
from pathlib import Path
from markdown_it import MarkdownIt

def main():
    md_path = Path("kich-ban.md")
    if not md_path.exists():
        print("kich-ban.md not found")
        return

    md_text = md_path.read_text(encoding="utf-8")
    md = MarkdownIt("commonmark").enable("table").enable("strikethrough")
    html_content = md.render(md_text)

    css = """
    @page {
        size: A4;
        margin: 14mm 14mm 14mm 14mm;
    }
    body {
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
        color: #1e293b;
        line-height: 1.5;
        font-size: 10.5pt;
        margin: 0;
        padding: 0;
    }
    h1 {
        font-size: 17pt;
        color: #0f172a;
        border-bottom: 2px solid #0284c7;
        padding-bottom: 4px;
        margin-top: 0;
        margin-bottom: 8px;
    }
    h2 {
        font-size: 13pt;
        color: #0369a1;
        border-bottom: 1px solid #cbd5e1;
        padding-bottom: 3px;
        margin-top: 16px;
        margin-bottom: 6px;
        page-break-after: avoid;
    }
    h3 {
        font-size: 11.5pt;
        color: #0f172a;
        margin-top: 12px;
        margin-bottom: 4px;
        page-break-after: avoid;
    }
    h4 {
        font-size: 10.5pt;
        color: #334155;
        margin-top: 8px;
        margin-bottom: 3px;
        page-break-after: avoid;
    }
    p, li {
        margin-top: 2px;
        margin-bottom: 4px;
    }
    blockquote {
        background: #f8fafc;
        border-left: 4px solid #0284c7;
        margin: 5px 0;
        padding: 5px 10px;
        color: #1e293b;
        font-style: normal;
    }
    blockquote p {
        margin: 2px 0;
    }
    table {
        width: 100%;
        border-collapse: collapse;
        margin: 8px 0;
        font-size: 9pt;
        page-break-inside: auto;
    }
    tr {
        page-break-inside: avoid;
        page-break-after: auto;
    }
    th, td {
        border: 1px solid #cbd5e1;
        padding: 5px 7px;
        text-align: left;
        vertical-align: top;
    }
    th {
        background-color: #f1f5f9;
        color: #0f172a;
        font-weight: 600;
    }
    code {
        background-color: #f1f5f9;
        color: #0284c7;
        padding: 1px 3px;
        border-radius: 3px;
        font-family: Consolas, 'Courier New', monospace;
        font-size: 8.5pt;
    }
    pre {
        background-color: #0f172a;
        color: #f8fafc;
        padding: 6px 10px;
        border-radius: 4px;
        font-family: Consolas, 'Courier New', monospace;
        font-size: 8pt;
        overflow-x: auto;
        page-break-inside: avoid;
        margin: 5px 0;
    }
    pre code {
        background-color: transparent;
        color: inherit;
        padding: 0;
    }
    hr {
        border: none;
        border-top: 1px solid #e2e8f0;
        margin: 10px 0;
    }
    strong {
        color: #0f172a;
    }
    """

    html_template = f"""<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<title>Kịch Bản Quay Video Demo — Reflex</title>
<style>{css}</style>
</head>
<body>
{html_content}
</body>
</html>"""

    html_path = Path("kich-ban.html")
    html_path.write_text(html_template, encoding="utf-8")
    print(f"Generated {html_path.resolve()}")

    # Tìm Chrome hoặc Edge
    chrome_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ]
    browser_exe = None
    for p in chrome_paths:
        if os.path.exists(p):
            browser_exe = p
            break

    if not browser_exe:
        print("No Chrome/Edge found to export PDF.")
        return

    pdf_path = Path("kich-ban.pdf").resolve()
    html_abs_url = html_path.resolve().as_uri()

    cmd = [
        browser_exe,
        "--headless",
        "--disable-gpu",
        "--run-all-compositor-stages-before-draw",
        f"--print-to-pdf={pdf_path}",
        html_abs_url,
    ]
    print(f"Exporting PDF using {browser_exe}...")
    subprocess.run(cmd, check=True)
    if pdf_path.exists():
        print(f"SUCCESS: PDF created at {pdf_path} ({pdf_path.stat().st_size} bytes)")
    else:
        print("ERROR: PDF was not generated.")

if __name__ == "__main__":
    main()
