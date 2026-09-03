#!/usr/bin/env python3
from pathlib import Path
import re

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
    pattern = re.compile(rf"(\b{re.escape(key)}\s*:\s*)(['\"])(.*?)(?<!\\)\2", re.S)
    m = pattern.search(text)
    if not m:
        return text
    escaped = value.replace('\\', '\\\\').replace('"', '\\"')
    return text[:m.start()] + m.group(1) + '"' + escaped + '"' + text[m.end():]


def main():
    text = MASTER.read_text(encoding="utf-8")

    for old, new in REPLACEMENTS.items():
        text = text.replace(old, new)

    # Remove any historical staff-image URL/path that explicitly belongs to TDC.
    text = re.sub(r"https?://[^\"'\s<>]*fukuoka-tdc[^\"'\s<>]*", "", text, flags=re.I)
    text = re.sub(r"[^\"'\s<>]*\/fukuoka-tdc\/[^\"'\s<>]*", "", text, flags=re.I)

    # MASTER defaults are intentionally generic/empty. Clinic values come only from payload.
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

    text = re.sub(
        r"<title[^>]*>.*?</title>",
        "<title data-shikakin-title=\"\">シカキンLPテンプレート | 歯科筋筋膜セラピー</title>",
        text,
        count=1,
        flags=re.S,
    )

    leaks = [value for value in FORBIDDEN if value and value in text]
    if leaks:
        raise SystemExit("MASTER still contains clinic-specific data: " + ", ".join(leaks))

    MASTER.write_text(text, encoding="utf-8")
    print("MASTER sanitized successfully")


if __name__ == "__main__":
    main()
