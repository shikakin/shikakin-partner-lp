#!/usr/bin/env python3
import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MASTER = ROOT / "master" / "index.html"


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


def inject_staff_runtime(text):
    """Always rebuild staff cards from the generated clinic config.

    Staff cards never use staff-photo fallbacks embedded in MASTER. This prevents
    a newly generated clinic from inheriting another clinic's doctor/therapist photo.
    """
    marker = "/* SHIKAKIN_DYNAMIC_STAFF_RUNTIME_V1 */"
    if marker in text:
        return text

    script = r'''
<script>
/* SHIKAKIN_DYNAMIC_STAFF_RUNTIME_V1 */
(function () {
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
    if (typeof SHIKAKIN_LP_CONFIG === 'undefined') return;
    rebuild('doctorStaffGrid', SHIKAKIN_LP_CONFIG.doctors);
    rebuild('therapistStaffGrid', SHIKAKIN_LP_CONFIG.therapists);
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


def validate_generated(text, doctors, therapists):
    for item in doctors + therapists:
        if item.get("name") and item["name"] not in text:
            raise SystemExit(f"staff name missing from generated HTML: {item['name']}")
        if item.get("photo") and item["photo"] not in text:
            raise SystemExit(f"staff photo missing from generated HTML: {item['name']}")
    if "SHIKAKIN_DYNAMIC_STAFF_RUNTIME_V1" not in text:
        raise SystemExit("dynamic staff runtime injection failed")


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

    scalar_fields = {
        "sourceWebsiteUrl": payload.get("website", ""),
        "clinicName": payload.get("clinicName", ""),
        "reservationUrl": payload.get("reservationUrl", ""),
        "lineUrl": payload.get("lineUrl", ""),
        "address": payload.get("address", ""),
        "tel": payload.get("tel", ""),
        "access": payload.get("access", ""),
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

    # Preserve all fixed MASTER images. Override only keys supplied for this clinic.
    image_overrides = dict(payload.get("images") or {})
    image_overrides["directorImage"] = doctors[0].get("photo", "") if doctors else ""
    image_overrides["therapistImage"] = therapists[0].get("photo", "") if therapists else ""
    for key, value in image_overrides.items():
        text = replace_scalar(text, key, value)

    if payload.get("clinicIntro"):
        text = text.replace("{{CLINIC_INTRO}}", payload["clinicIntro"])

    text = re.sub(
        r"<title[^>]*>.*?</title>",
        f"<title>{payload.get('clinicName','')} | シカキンセラピー</title>",
        text,
        count=1,
        flags=re.S,
    )

    text = inject_staff_runtime(text)
    validate_generated(text, doctors, therapists)

    target = ROOT / slug
    target.mkdir(parents=True, exist_ok=True)
    (target / "index.html").write_text(text, encoding="utf-8")
    print(f"Generated: {target / 'index.html'}")


if __name__ == "__main__":
    main()
