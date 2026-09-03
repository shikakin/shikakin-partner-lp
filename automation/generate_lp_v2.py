#!/usr/bin/env python3
import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MASTER = ROOT / "master" / "index.html"

FORBIDDEN_LEGACY = (
    "福岡歯科 統合医療研究所DC（歯科室）",
    "福岡歯科 TDC",
    "https://418.co.jp/tdc/",
    "〒103-0025",
    "東京都中央区日本橋茅場町1-10-5 エフワンビル4F",
    "03-3662-0222",
    "0336620222",
    "藤 兼次",
    "山本 江里香",
    "/fukuoka-tdc/",
)


def replace_scalar(text, key, value):
    marker = key + ":"
    start = text.find(marker)
    if start < 0:
        print(f"WARN: scalar key not found: {key}")
        return text
    pos = start + len(marker)
    while pos < len(text) and text[pos].isspace():
        pos += 1
    if pos >= len(text) or text[pos] not in ('"', "'"):
        print(f"WARN: scalar key is not quoted: {key}")
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
            encoded = json.dumps(value or "", ensure_ascii=False)
            return text[:pos] + encoded + text[i + 1:]
        i += 1
    raise SystemExit(f"Unterminated scalar: {key}")


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
    raise SystemExit(f"Unbalanced {open_char}{close_char}")


def replace_array(text, key, value):
    marker = key + ":"
    pos = text.find(marker)
    if pos < 0:
        print(f"WARN: array key not found: {key}")
        return text
    start = text.find("[", pos + len(marker))
    if start < 0:
        raise SystemExit(f"Array start not found: {key}")
    end = find_balanced(text, start, "[", "]")
    encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return text[:start] + encoded + text[end:]


def replace_title(text, clinic_name):
    start = text.find("<title")
    if start < 0:
        return text
    end = text.find("</title>", start)
    if end < 0:
        return text
    end += len("</title>")
    return text[:start] + f"<title>{clinic_name} | シカキンセラピー</title>" + text[end:]


def normalize_staff(items, role_default):
    out = []
    for item in items or []:
        if not item or not item.get("name"):
            continue
        photo = str(item.get("photo") or item.get("image") or "").strip()
        out.append({
            "name": str(item.get("name") or ""),
            "role": str(item.get("role") or role_default),
            "title": str(item.get("title") or ""),
            "image": photo,
            "photo": photo,
        })
    return out


def tel_href(tel):
    compact = re.sub(r"[^0-9+]", "", str(tel or ""))
    return f"tel:{compact}" if compact else ""


def inject_runtime(text):
    marker = "/* SHIKAKIN_DYNAMIC_RUNTIME_V3 */"
    if marker in text:
        return text
    script = r'''
<script>
/* SHIKAKIN_DYNAMIC_RUNTIME_V3 */
(function () {
  function cfg() { return (typeof SHIKAKIN_LP_CONFIG !== 'undefined' && SHIKAKIN_LP_CONFIG) ? SHIKAKIN_LP_CONFIG : {}; }
  function setHref(selector, href) {
    document.querySelectorAll(selector).forEach(function (el) {
      if (href) el.setAttribute('href', href); else el.removeAttribute('href');
    });
  }
  function card(item) {
    const article = document.createElement('article'); article.className = 'staff-card';
    const photoWrap = document.createElement('div'); photoWrap.className = 'staff-photo';
    const src = String((item && (item.photo || item.image)) || '').trim();
    if (src) { const img = document.createElement('img'); img.src = src; img.alt = String(item.name || 'スタッフ'); img.loading = 'eager'; photoWrap.appendChild(img); }
    else { const p = document.createElement('div'); p.className = 'staff-photo-placeholder'; p.textContent = 'PHOTO'; photoWrap.appendChild(p); }
    const meta = document.createElement('div'); meta.className = 'staff-meta';
    const pos = document.createElement('div'); pos.className = 'staff-position'; pos.textContent = [item.role, item.title].filter(Boolean).join(' / ');
    const name = document.createElement('div'); name.className = 'staff-name'; name.textContent = String(item.name || '');
    meta.appendChild(pos); meta.appendChild(name); article.appendChild(photoWrap); article.appendChild(meta); return article;
  }
  function rebuild(id, items) {
    const grid = document.getElementById(id); if (!grid) return; grid.replaceChildren();
    (Array.isArray(items) ? items : []).filter(x => x && x.name).forEach(x => grid.appendChild(card(x)));
  }
  function apply() {
    const c = cfg();
    const phone = String(c.tel || '').replace(/[^0-9+]/g, '');
    const phoneUrl = phone ? ('tel:' + phone) : '';
    const main = String(c.ctaMainUrl || c.reservationUrl || c.lineUrl || phoneUrl || c.sourceWebsiteUrl || '').trim();
    setHref('[data-href="ctaMainUrl"]', main);
    setHref('[data-href="reservationUrl"]', String(c.reservationUrl || main).trim());
    setHref('[data-href="lineUrl"]', String(c.lineUrl || c.sourceWebsiteUrl || main).trim());
    setHref('[data-href="sourceWebsiteUrl"]', String(c.sourceWebsiteUrl || main).trim());
    rebuild('doctorStaffGrid', c.doctors); rebuild('therapistStaffGrid', c.therapists);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', apply, { once:true }); else apply();
  window.addEventListener('load', apply, { once:true });
})();
</script>
'''
    return text.replace("</body>", script + "\n</body>", 1) if "</body>" in text else text + script


def validate_master(text):
    if not text.strip():
        raise SystemExit("MASTER is empty")
    leaks = [v for v in FORBIDDEN_LEGACY if v and v in text]
    if leaks:
        raise SystemExit("MASTER contains forbidden clinic data: " + ", ".join(leaks))


def validate_generated(text, payload, doctors, therapists, cta_main_url):
    required = {
        "clinicName": payload.get("clinicName"),
        "website": payload.get("website"),
        "address": payload.get("address"),
        "tel": payload.get("tel"),
        "access": payload.get("access"),
    }
    for key, value in required.items():
        value = str(value or "").strip()
        if value and value not in text:
            raise SystemExit(f"{key} missing from generated HTML")
    for item in doctors + therapists:
        if item["name"] not in text:
            raise SystemExit(f"staff name missing: {item['name']}")
        if item["photo"] and item["photo"] not in text:
            raise SystemExit(f"staff photo missing: {item['name']}")
    if cta_main_url and cta_main_url not in text:
        raise SystemExit("CTA URL missing from generated HTML")
    leaks = [v for v in FORBIDDEN_LEGACY if v and v in text]
    if leaks:
        raise SystemExit("Generated HTML contains forbidden clinic data: " + ", ".join(leaks))
    if "SHIKAKIN_DYNAMIC_RUNTIME_V3" not in text:
        raise SystemExit("runtime injection failed")


def main():
    payload = json.loads(os.environ.get("CLINIC_PAYLOAD", "{}"))
    slug = re.sub(r"[^a-z0-9-]", "-", str(payload.get("slug") or "").lower()).strip("-")
    if not slug:
        raise SystemExit("slug is required")
    if slug in {"master", "fukuoka-tdc", "yutenji", "sangu-dental99", "utoh", "automation", ".github"}:
        raise SystemExit(f"protected slug: {slug}")
    if not MASTER.exists():
        raise SystemExit(f"MASTER not found: {MASTER}")

    text = MASTER.read_text(encoding="utf-8")
    validate_master(text)

    doctors = normalize_staff(payload.get("doctors"), "院長")
    therapists = normalize_staff(payload.get("therapists"), "シカキンセラピスト")
    clinic_name = str(payload.get("clinicName") or "")
    website = str(payload.get("website") or "").strip()
    reservation_url = str(payload.get("reservationUrl") or "").strip()
    line_url = str(payload.get("lineUrl") or "").strip()
    tel = str(payload.get("tel") or "").strip()
    cta_main_url = reservation_url or line_url or tel_href(tel) or website

    scalar_fields = {
        "sourceWebsiteUrl": website,
        "clinicName": clinic_name,
        "clinicShort": clinic_name,
        "reservationUrl": reservation_url,
        "lineUrl": line_url,
        "address": payload.get("address", ""),
        "tel": tel,
        "access": payload.get("access", ""),
        "ctaMainLabel": "初回相談はこちら",
        "ctaMainUrl": cta_main_url,
        "reservationCtaLabel": "WEB予約はこちら" if reservation_url else "ご予約・ご相談",
        "lineCtaLabel": "LINEで相談" if line_url else "医院公式サイト",
        "directorName": doctors[0]["name"] if doctors else "",
        "directorRole": doctors[0]["role"] if doctors else "院長",
        "therapistName": therapists[0]["name"] if therapists else "",
        "therapistRole": therapists[0]["role"] if therapists else "シカキンセラピスト",
        "postalCode": payload.get("postalCode", ""),
        "directorImage": doctors[0]["photo"] if doctors else "",
        "therapistImage": therapists[0]["photo"] if therapists else "",
    }
    for key, value in scalar_fields.items():
        text = replace_scalar(text, key, value)

    text = replace_array(text, "doctors", doctors)
    text = replace_array(text, "therapists", therapists)

    for key, value in dict(payload.get("images") or {}).items():
        if key not in {"directorImage", "therapistImage"}:
            text = replace_scalar(text, key, value)

    if payload.get("clinicIntro"):
        text = text.replace("{{CLINIC_INTRO}}", str(payload["clinicIntro"]))

    text = replace_title(text, clinic_name)
    text = inject_runtime(text)
    validate_generated(text, payload, doctors, therapists, cta_main_url)

    target = ROOT / slug
    target.mkdir(parents=True, exist_ok=True)
    out = target / "index.html"
    out.write_text(text, encoding="utf-8")
    print(f"Generated: {out}")


if __name__ == "__main__":
    main()
