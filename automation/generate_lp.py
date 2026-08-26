#!/usr/bin/env python3
import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MASTER = ROOT / "fukuoka-tdc" / "index.html"


def js_string(value):
    return json.dumps(value or "", ensure_ascii=False)


def replace_scalar(text, key, value):
    pattern = re.compile(rf"(\b{re.escape(key)}\s*:\s*)(['\"])(.*?)(?<!\\)\2", re.S)
    m = pattern.search(text)
    if not m:
        print(f"WARN: scalar key not found: {key}")
        return text
    replacement = m.group(1) + js_string(value)
    return text[:m.start()] + replacement + text[m.end():]


def find_balanced(text, start, open_char, close_char):
    depth = 0
    quote = None
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if quote:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == quote:
                quote = None
            continue
        if ch in ("'", '"', '`'):
            quote = ch
            continue
        if ch == open_char:
            depth += 1
        elif ch == close_char:
            depth -= 1
            if depth == 0:
                return i + 1
    raise ValueError(f"Unbalanced {open_char}{close_char}")


def replace_array(text, key, value):
    m = re.search(rf"\b{re.escape(key)}\s*:\s*\[", text)
    if not m:
        print(f"WARN: array key not found: {key}")
        return text
    start = text.find('[', m.start())
    end = find_balanced(text, start, '[', ']')
    value_js = json.dumps(value, ensure_ascii=False, separators=(',', ':'))
    return text[:start] + value_js + text[end:]


def replace_object(text, key, value):
    m = re.search(rf"\b{re.escape(key)}\s*:\s*\{{", text)
    if not m:
        print(f"WARN: object key not found: {key}")
        return text
    start = text.find('{', m.start())
    end = find_balanced(text, start, '{', '}')
    value_js = json.dumps(value, ensure_ascii=False, separators=(',', ':'))
    return text[:start] + value_js + text[end:]


def normalize_staff(items, role_default):
    out = []
    for item in items or []:
        if not item or not item.get("name"):
            continue
        obj = {
            "name": item.get("name", ""),
            "role": item.get("role", role_default),
            "title": item.get("title", ""),
            "photo": item.get("photo", ""),
        }
        out.append(obj)
    return out


def main():
    payload_raw = os.environ.get("CLINIC_PAYLOAD", "{}")
    payload = json.loads(payload_raw)
    slug = re.sub(r"[^a-z0-9-]", "-", (payload.get("slug") or "").lower()).strip('-')
    if not slug:
        raise SystemExit("slug is required")
    if slug in {"fukuoka-tdc", "yutenji", "sangu-dental99", "utoh", "automation", ".github"}:
        raise SystemExit(f"protected slug: {slug}")

    text = MASTER.read_text(encoding="utf-8")

    scalar_fields = {
        "sourceWebsiteUrl": payload.get("website", ""),
        "clinicName": payload.get("clinicName", ""),
        "reservationUrl": payload.get("reservationUrl", ""),
        "lineUrl": payload.get("lineUrl", ""),
        "address": payload.get("address", ""),
        "tel": payload.get("tel", ""),
        "access": payload.get("access", ""),
        "directorName": (payload.get("doctors") or [{}])[0].get("name", "") if payload.get("doctors") else "",
        "directorRole": (payload.get("doctors") or [{}])[0].get("role", "院長") if payload.get("doctors") else "院長",
        "therapistName": (payload.get("therapists") or [{}])[0].get("name", "") if payload.get("therapists") else "",
    }
    for key, value in scalar_fields.items():
        text = replace_scalar(text, key, value)

    doctors = normalize_staff(payload.get("doctors"), "院長")
    therapists = normalize_staff(payload.get("therapists"), "シカキンセラピスト")
    text = replace_array(text, "doctors", doctors)
    text = replace_array(text, "therapists", therapists)

    if payload.get("images"):
        text = replace_object(text, "images", payload["images"])

    if payload.get("clinicIntro"):
        # Optional placeholders can be added to MASTER later. Safe no-op for current MASTER.
        text = text.replace("{{CLINIC_INTRO}}", payload["clinicIntro"])

    # Make title unique even if the template title is not fully data-driven.
    text = re.sub(r"<title[^>]*>.*?</title>", f"<title>{payload.get('clinicName','')} | シカキンセラピー</title>", text, count=1, flags=re.S)

    target = ROOT / slug
    target.mkdir(parents=True, exist_ok=True)
    (target / "index.html").write_text(text, encoding="utf-8")
    print(f"Generated: {target / 'index.html'}")


if __name__ == "__main__":
    main()
