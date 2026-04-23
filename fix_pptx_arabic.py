# -*- coding: utf-8 -*-
"""Apply Arabic text fixes to extracted OOXML slides and repackage PPTX."""
import pathlib
import shutil

ROOT = pathlib.Path(__file__).resolve().parent
EXTRACT = ROOT / "pptx_extract"
SLIDES = EXTRACT / "ppt" / "slides"
OUT_PPTX = pathlib.Path(r"d:\الذكاء الاصطناعي في التعليم_مصحح.pptx")


def remove_second_xml_text(haystack: str, inner: str) -> str:
    needle = f"<a:t>{inner}</a:t>"
    first = haystack.find(needle)
    if first == -1:
        return haystack
    second = haystack.find(needle, first + len(needle))
    if second == -1:
        return haystack
    return haystack[:second] + "<a:t></a:t>" + haystack[second + len(needle) :]


def fix_slide7(text: str) -> str:
    old_title = (
        "<a:t>التحديات والمخاوف المتعلقة بالذكاء الاصط</a:t></a:r><a:r>"
        '<a:rPr lang="ar-EG" sz="2999"><a:gradFill><a:gsLst><a:gs pos="0"><a:srgbClr val="CDFFD8"><a:alpha val="100000"/></a:srgbClr></a:gs><a:gs pos="100000"><a:srgbClr val="94B9FF"><a:alpha val="100000"/></a:srgbClr></a:gs></a:gsLst><a:lin ang="2700000"/></a:gradFill><a:latin typeface="Work Sans"/><a:ea typeface="Work Sans"/><a:cs typeface="Work Sans"/><a:sym typeface="Work Sans"/><a:rtl val="true"/></a:rPr><a:t>ناعي في التعليم</a:t></a:r>'
    )
    new_title = '<a:t>التحديات والمخاوف المتعلقة بالذكاء الاصطناعي في التعليم</a:t></a:r>'
    text = text.replace(old_title, new_title)

    old_p = (
        "<a:t>على الرغم م</a:t></a:r><a:r>"
        '<a:rPr lang="ar-EG" sz="1799"><a:gradFill><a:gsLst><a:gs pos="0"><a:srgbClr val="CDFFD8"><a:alpha val="100000"/></a:srgbClr></a:gs><a:gs pos="100000"><a:srgbClr val="94B9FF"><a:alpha val="100000"/></a:srgbClr></a:gs></a:gsLst><a:lin ang="2700000"/></a:gradFill><a:latin typeface="Work Sans"/><a:ea typeface="Work Sans"/><a:cs typeface="Work Sans"/><a:sym typeface="Work Sans"/><a:rtl val="true"/></a:rPr><a:t>ن الفوائد الكبيرة للذكاء الاصطناعي في التعليم، إلا أن هناك عددًا من التحديات التي يجب الانتباه إليها، ومن أبرزها:</a:t></a:r>'
    )
    new_p = '<a:t>على الرغم من الفوائد الكبيرة للذكاء الاصطناعي في التعليم، إلا أن هناك عددًا من التحديات التي يجب الانتباه إليها، ومن أبرزها:</a:t></a:r>'
    text = text.replace(old_p, new_p)
    return text


def main() -> None:
    s7 = SLIDES / "slide7.xml"
    s7.write_text(fix_slide7(s7.read_text(encoding="utf-8")), encoding="utf-8")

    s5 = SLIDES / "slide5.xml"
    t5 = s5.read_text(encoding="utf-8")
    t5 = t5.replace(
        "<a:t>.لتوصية بالمحتوى المناسب:</a:t>",
        "<a:t>. التوصية بالمحتوى المناسب:</a:t>",
    )
    s5.write_text(t5, encoding="utf-8")

    s11 = SLIDES / "slide11.xml"
    t11 = s11.read_text(encoding="utf-8").replace(
        "<a:t>الشكر والرخصة</a:t>", "<a:t>الشكر والتقدير</a:t>"
    )
    s11.write_text(t11, encoding="utf-8")

    s2 = SLIDES / "slide2.xml"
    t2 = s2.read_text(encoding="utf-8")
    # تذييل مكرر لـ «محاور العرض» بينما العنوان مقسوم «محاور» + « العرض»
    t2 = t2.replace("<a:t>محاور العرض</a:t>", "<a:t></a:t>", 1)
    s2.write_text(t2, encoding="utf-8")

    s3 = SLIDES / "slide3.xml"
    s3.write_text(
        remove_second_xml_text(s3.read_text(encoding="utf-8"), "المقدمة"),
        encoding="utf-8",
    )

    s9 = SLIDES / "slide9.xml"
    s9.write_text(
        remove_second_xml_text(s9.read_text(encoding="utf-8"), "الخاتمة"),
        encoding="utf-8",
    )

    arch = ROOT / "ppt_ar_fixed"
    if arch.with_suffix(".zip").exists():
        arch.with_suffix(".zip").unlink()
    shutil.make_archive(str(arch), "zip", root_dir=EXTRACT)
    zpath = arch.with_suffix(".zip")
    if OUT_PPTX.exists():
        OUT_PPTX.unlink()
    shutil.move(str(zpath), str(OUT_PPTX))
    print("OK")


if __name__ == "__main__":
    main()
