# -*- coding: utf-8 -*-
import re
import pathlib
slides_dir = pathlib.Path(__file__).parent / "pptx_extract" / "ppt" / "slides"
out_lines = []
for path in sorted(slides_dir.glob("slide*.xml"), key=lambda p: int(re.search(r"(\d+)", p.stem).group(1))):
    # Join runs per paragraph is complex; simpler: list each a:t
    raw = path.read_text(encoding="utf-8")
    runs = re.findall(r"<a:t[^>]*>([^<]*)</a:t>", raw)
    # unescape common entities
    def unesc(s):
        return (
            s.replace("&amp;", "&")
            .replace("&lt;", "<")
            .replace("&gt;", ">")
            .replace("&quot;", '"')
            .replace("&#xa;", "\n")
        )

    runs = [unesc(r) for r in runs]
    out_lines.append(f"=== {path.name} ({len(runs)} runs) ===")
    for i, r in enumerate(runs):
        out_lines.append(f"  [{i:03d}] {r}")
    out_lines.append("--- ASSEMBLED (concat) ---")
    out_lines.append("".join(runs))
    out_lines.append("")

pathlib.Path(__file__).parent.joinpath("ppt_full_audit.txt").write_text(
    "\n".join(out_lines), encoding="utf-8"
)
print("wrote ppt_full_audit.txt")
