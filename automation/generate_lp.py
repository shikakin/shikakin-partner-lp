#!/usr/bin/env python3
import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MASTER = ROOT / "master" / "index.html"

LEGACY_TDC = {
    "clinic_full": "福岡歯科 統合医療研究所DC（歯科室）",
    "clinic_short": "福岡歯科 TDC",
    "website": "https://418.co.jp/tdc/",
    "postal": "〒103-0025",
    "address": "東京都中央区日本橋茅場町1-10-5 エフワンビル4F",
    "tel": "03-3662-0222",
    "tel_compact": "0336620222",
    "director": "藤 兼次",
    "therapist": "山本 江里香",
}


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


def normalize_staff(items, role_default):
    out = []
    for item in items or []:
        if not item or not item.get("name"):
            continue
        photo = (item.get("photo") or item.get("image") or "").strip()
        out.append({
            "name": item.get("name", ""),
            "role": item.get("role", role_default),
            "title": item.get("title", ""),
            "image": photo,
            "photo": photo,
        })
    return out


def tel_href(tel):
    compact = re.sub(r"[^0-9+]", "", str(tel or ""))
    return f"tel:{compact}" if compact else ""


def sanitize_legacy_tdc(text, payload, doctors, therapists):
    """Remove clinic-specific TDC values that were embedded in the historical MASTER."""
    clinic_name = str(payload.get("clinicName") or "認定パートナー歯科医院")
    website = str(payload.get("website") or "")
    address = str(payload.get("address") or "")
    tel = str(payload.get("tel") or "")
    director = doctors[0].get("name", "") if doctors else ""
    therapist = therapists[0].get("name", "") if therapists else ""

    replacements = {
        LEGACY_TDC["clinic_full"]: clinic_name,
        LEGACY_TDC["clinic_short"]: clinic_name,
        LEGACY_TDC["website"]: website,
        LEGACY_TDC["postal"]: "",
        LEGACY_TDC["address"]: address,
        LEGACY_TDC["tel"]: tel,
        LEGACY_TDC["tel_compact"]: re.sub(r"[^0-9+]", "", tel),
        LEGACY_TDC["director"]: director,
        LEGACY_TDC["therapist"]: therapist,
    }
    for old, new in replacements.items():
        if old:
            text = text.replace(old, new)

    # Remove any historical image URL/path that explicitly references fukuoka-tdc.
    text = re.sub(r"https?://[^\"'\s<>]*fukuoka-tdc[^\"'\s<>]*", "", text, flags=re.I)
    text = re.sub(r"[^\"'\s<>]*\/fukuoka-tdc\/[^\"'\s<>]*", "", text, flags=re.I)
    return text


def inject_runtime(text):
    marker = "/* SHIKAKIN_DYNAMIC_RUNTIME_V2 */"
    if marker in text:
        return text

    script = r'''
<script>
/* SHIKAKIN_DYNAMIC_RUNTIME_V2 */
(function () {
  function getConfig() {
    return (typeof SHIKAKIN_LP_CONFIG !== 'undefined' && SHIKAKIN_LP_CONFIG) ? SHIKAKIN_LP_CONFIG : {};
  }

  function setHref(selector, href) {
    if (!href) return;
    document.querySelectorAll(selector).forEach(function (el) {
      el.setAttribute('href', href);
    });
  }

  function buildStaffCard(item) {
    const article = document.createElement('article');
    article.className = 'staff-card';

    const photoWrap = document.createElement('div');
    photoWrap.className = 'staff-photo';
    const src = String((item && (item.photo || item.image)) || '').trim();
    if (src) {
      const img = document.createElement('img');
      img.src = src;
      img.alt = String((item && item.name) || 'スタッフ');
      img.loading = 'eager';
      photoWrap.appendChild(img);
    } else {
      const placeholder = document.createElement('div');
      placeholder.className = 'staff-photo-placeholder';
      placeholder.textContent = 'PHOTO';
      photoWrap.appendChild(placeholder);
    }

    const meta = document.createElement('div');
    meta.className = 'staff-meta';
    const position = document.createElement('div');
    position.className = 'staff-position';
    position.textContent = [item && item.role, item && item.title].filter(Boolean).join(' / ');
    const name = document.createElement('div');
    name.className = 'staff-name';
    name.textContent = String((item && item.name) || '');
    meta.appendChild(position);
    meta.appendChild(name);
    article.appendChild(photoWrap);
    article.appendChild(meta);
    return article;
  }

  function rebuild(containerId, items) {
    const grid = document.getElementById(containerId);
    if (!grid) return;
    grid.replaceChildren();
    (Array.isArray(items) ? items : []).filter(item => item && item.name).forEach(item => {
      grid.appendChild(buildStaffCard(item));
    });
  }

  function apply() {
    const cfg = getConfig();
    const phone = String(cfg.tel || '').replace(/[^0-9+]/g, '');
    const phoneUrl = phone ? ('tel:' + phone) : '';
    const mainUrl = String(cfg.ctaMainUrl || cfg.reservationUrl || cfg.lineUrl || phoneUrl || cfg.sourceWebsiteUrl || '').trim();
    const reservationUrl = String(cfg.reservationUrl || mainUrl).trim();
    const lineUrl = String(cfg.lineUrl || cfg.sourceWebsiteUrl || mainUrl).trim();
    const websiteUrl = String(cfg.sourceWebsiteUrl || mainUrl).trim();

    // Always overwrite every clinic-specific link at runtime. Static MASTER href values are never trusted.
    setHref('[data-href="ctaMainUrl"]', mainUrl);
    setHref('[data-href="reservationUrl"]', reservationUrl);
    setHref('[data-href="lineUrl"]', lineUrl);
    setHref('[data-href="sourceWebsiteUrl"]', websiteUrl);

    rebuild('doctorStaffGrid', cfg.doctors);
    rebuild('therapistStaffGrid', cfg.therapists);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', apply, { once: true });
  } else {
    apply();
  }
  window.addEventListener('load', apply, { once: true });
})();
</script>
'''
    if "</body>" in text:
        return text.replace("</body>", script + "\n</body>", 1)
    return text + script


def validate_generated(text, payload, doctors, therapists, cta_main_url):
    for item in doctors + therapists:
        if item.get("name") and item["name"] not in text:
            raise SystemExit(f"staff name missing from generated HTML: {item['name']}")
        if item.get("photo") and item["photo"] not in text:
            raise SystemExit(f"staff photo missing from generated HTML: {item['name']}")

    for key in ("clinicName", "website", "address", "tel", "access"):
        value = str(payload.get(key) or "").strip()
        if value and value not in text:
            raise SystemExit(f"{key} missing from generated HTML")

    if cta_main_url and cta_main_url not in text:
        raise SystemExit("CTA URL missing from generated HTML")
    if "SHIKAKIN_DYNAMIC_RUNTIME_V2" not in text:
        raise SystemExit("dynamic runtime injection failed")

    # A new clinic must never inherit historical TDC content.
    current_clinic = str(payload.get("clinicName") or "")
    if current_clinic != LEGACY_TDC["clinic_full"]:
        forbidden = [
            LEGACY_TDC["clinic_full"],
            LEGACY_TDC["clinic_short"],
            LEGACY_TDC["website"],
            LEGACY_TDC["address"],
            LEGACY_TDC["tel"],
            LEGACY_TDC["tel_compact"],
            "/fukuoka-tdc/",
        ]
        leaks = [value for value in forbidden if value and value in text]
        if leaks:
            raise SystemExit("legacy clinic data remains in generated HTML: " + ", ".join(leaks))


def main():
    payload_raw = os.environ.get("CLINIC_PAYLOAD", "{}")
    payload = json.loads(payload_raw)
    slug = re.sub(r"[^a-z0-9-]", "-", (payload.get("slug") or "").lower()).strip('-')
    if not slug:
        raise SystemExit("slug is required")
    if slug in {"master", "fukuoka-tdc", "yutenji", "sangu-dental99", "utoh", "automation", ".github"}:
        raise SystemExit(f"protected slug: {slug}")
    if not MASTER.exists():
        raise SystemExit(f"MASTER not found: {MASTER}")

    text = MASTER.read_text(encoding="utf-8")
    doctors = normalize_staff(payload.get("doctors"), "院長")
    therapists = normalize_staff(payload.get("therapists"), "シカキンセラピスト")

    website = str(payload.get("website") or "").strip()
    reservation_url = str(payload.get("reservationUrl") or "").strip()
    line_url = str(payload.get("lineUrl") or "").strip()
    tel = str(payload.get("tel") or "").strip()
    phone_url = tel_href(tel)
    cta_main_url = reservation_url or line_url or phone_url or website

    # First neutralize every known clinic-specific value inherited from the historical TDC file.
    text = sanitize_legacy_tdc(text, payload, doctors, therapists)

    scalar_fields = {
        "sourceWebsiteUrl": website,
        "clinicName": payload.get("clinicName", ""),
        "clinicShort": payload.get("clinicName", ""),
        "reservationUrl": reservation_url,
        "lineUrl": line_url,
        "address": payload.get("address", ""),
        "tel": tel,
        "access": payload.get("access", ""),
        "ctaMainLabel": "初回相談はこちら",
        "ctaMainUrl": cta_main_url,
        "reservationCtaLabel": "WEB予約はこちら" if reservation_url else "ご予約・ご相談",
        "lineCtaLabel": "LINEで相談" if line_url else "医院公式サイト",
        "directorName": doctors[0].get("name", "") if doctors else "",
        "directorRole": doctors[0].get("role", "院長") if doctors else "院長",
        "therapistName": therapists[0].get("name", "") if therapists else "",
        "therapistRole": therapists[0].get("role", "シカキンセラピスト") if therapists else "シカキンセラピスト",
        "postalCode": payload.get("postalCode", ""),
    }
    for key, value in scalar_fields.items():
        text = replace_scalar(text, key, value)

    text = replace_array(text, "doctors", doctors)
    text = replace_array(text, "therapists", therapists)

    # Preserve common MASTER images. Only clinic staff images are overridden.
    image_overrides = dict(payload.get("images") or {})
    image_overrides["directorImage"] = doctors[0].get("photo", "") if doctors else ""
    image_overrides["therapistImage"] = therapists[0].get("photo", "") if therapists else ""
    for key, value in image_overrides.items():
        text = replace_scalar(text, key, value)

    if payload.get("clinicIntro"):
        text = text.replace("{{CLINIC_INTRO}}", str(payload["clinicIntro"]))

    text = re.sub(
        r"<title[^>]*>.*?</title>",
        f"<title>{payload.get('clinicName','')} | シカキンセラピー</title>",
        text,
        count=1,
        flags=re.S,
    )

    text = inject_runtime(text)
    validate_generated(text, payload, doctors, therapists, cta_main_url)

    target = ROOT / slug
    target.mkdir(parents=True, exist_ok=True)
    (target / "index.html").write_text(text, encoding="utf-8")
    print(f"Generated: {target / 'index.html'}")


if __name__ == "__main__":
    main()
