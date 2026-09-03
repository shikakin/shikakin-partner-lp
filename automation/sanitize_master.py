#!/usr/bin/env python3
from pathlib import Path

MASTER = Path(__file__).resolve().parents[1] / "master" / "index.html"

# Historical clinic-specific values that must never live in MASTER.
REPLACEMENTS = {
    "福岡歯科 統合医療研究所DC（歯科室）": "〇〇歯科医院",
    "福岡歯科 TDC": "〇〇歯科医院",
    "https://418.co.jp/tdc/": "",
    "〒103-0025": "",
    "東京都中央区日本橋茅場町1-10-5 エフワンビル4F": "",
    "03-3662-0222": "",
    "0336620222": "",
    "藤 兼次": "",
    "山本 江里香": "",
}

FORBIDDEN = tuple(REPLACEMENTS.keys()) + ("/fukuoka-tdc/",)


def set_scalar(text, key, value):
    """Replace a quoted JS scalar in linear time.

    MASTER contains multi-megabyte base64 images, so whole-document DOTALL regexes
    are intentionally avoided.
    """
    marker = key + ":"
    start = text.find(marker)
    if start < 0:
        return text

    pos = start + len(marker)
    while pos < len(text) and text[pos].isspace():
        pos += 1
    if pos >= len(text) or text[pos] not in ('"', "'"):
        return text

    quote = text[pos]
    value_start = pos + 1
    i = value_start
    escaped = False
    while i < len(text):
        ch = text[i]
        if escaped:
            escaped = False
        elif ch == "\\":
            escaped = True
        elif ch == quote:
            escaped_value = value.replace("\\", "\\\\").replace(quote, "\\" + quote)
            return text[:value_start] + escaped_value + text[i:]
        i += 1
    return text


def replace_title(text):
    start = text.find("<title")
    if start < 0:
        return text
    end = text.find("</title>", start)
    if end < 0:
        return text
    end += len("</title>")
    replacement = '<title data-shikakin-title="">シカキンLPテンプレート | 歯科筋筋膜セラピー</title>'
    return text[:start] + replacement + text[end:]


def main():
    text = MASTER.read_text(encoding="utf-8")
    if not text.strip():
        raise SystemExit("MASTER is empty")

    # Literal replacements are linear and safe even with embedded base64 images.
    for old, new in REPLACEMENTS.items():
        text = text.replace(old, new)

    # MASTER defaults are generic/empty. Clinic values come only from payload.
    defaults = {
        "sourceWebsiteUrl": "",
        "clinicName": "〇〇歯科医院",
        "clinicShort": "〇〇歯科医院",
        "reservationUrl": "",
        "lineUrl": "",
        "address": "",
        "tel": "",
        "access": "",
        "ctaMainUrl": "",
        "directorName": "",
        "directorRole": "院長",
        "therapistName": "",
        "therapistRole": "シカキンセラピスト",
        "postalCode": "",
        "directorImage": "",
        "therapistImage": "",
    }
    for key, value in defaults.items():
        text = set_scalar(text, key, value)

    text = replace_title(text)

    leaks = [value for value in FORBIDDEN if value and value in text]
    if leaks:
        raise SystemExit("MASTER still contains clinic-specific data: " + ", ".join(leaks))

    MASTER.write_text(text, encoding="utf-8")
    print("MASTER sanitized successfully")


if __name__ == "__main__":
    main()
