"""Rebuild selected, source-checked paraphrases from archived WHO sources. Not a crawler or OCR service."""

import hashlib
import html
import json
import re
from pathlib import Path

r = Path(__file__).resolve().parents[1]
raw = r / "data/raw/who/2026-11-20"
out = r / "data/processed/who/2026-11-20"
out.mkdir(parents=True, exist_ok=True)
manifest = r / "data/sources/who/2026-11-20/catalog.json"
if manifest.exists():
    for source in json.loads(manifest.read_text())["sources"]:
        archived = r / source["raw_file"]
        if hashlib.sha256(archived.read_bytes()).hexdigest() != source["raw_sha256"]:
            raise ValueError("WHO snapshot changed; re-review before preparing")
body = None
for x in re.findall(
    r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
    (raw / "infant-feeding.html").read_text(),
    re.DOTALL,
):
    try:
        d = json.JSONDecoder().raw_decode(x.strip())[0]
    except ValueError:
        continue
    if d.get("headline") == "Infant and young child feeding":
        body = d["description"]
        break
assert body
sections = re.split(r"<h2>(.*?)</h2>", body)
for i in range(1, len(sections), 2):
    if sections[i] in ["Breastfeeding", "Complementary feeding"]:
        text = html.unescape(re.sub("<[^>]+>", " ", sections[i + 1]))
        text = re.sub(r"\s+", " ", text).strip()
        (out / (sections[i].lower().replace(" ", "-") + ".source.txt")).write_text(text)
        print(sections[i], text)
items = [
    (
        "five-keys",
        "Five keys to safer food manual",
        "https://www.who.int/publications/i/item/9789241594639",
        "2006-05-15",
        "five-keys.pdf",
        [
            (
                "Keep clean | PDF page 13; printed 12",
                "Wash hands before food handling, repeatedly while preparing it, and after toilet use. Clean and sanitize food-contact equipment and surfaces. Keep insects, other pests and animals away from kitchens and food.",
            ),
            (
                "Separate raw and cooked | PDF page 16; printed 15",
                "Keep uncooked meat, poultry and seafood apart from other foods. Use different knives and boards for raw ingredients. Covered containers prevent raw and prepared foods from touching. Raw-food juices can transfer harmful microorganisms.",
            ),
            (
                "Cook thoroughly | PDF page 17; printed 16",
                "Thoroughly cook meat, poultry, eggs and seafood and reheat cooked dishes thoroughly. Soups and stews should boil and reach 70 degrees Celsius. Ideally check with a thermometer.",
            ),
            (
                "Keep food at safe temperatures | PDF page 19; printed 18",
                "Cooked food should spend no more than two hours at room temperature. Refrigerate perishable and cooked foods promptly, preferably below 5 degrees Celsius; hold hot meals above 60 degrees before serving. Refrigeration does not stop every dangerous microorganism. Avoid prolonged refrigerated storage and room-temperature thawing.",
            ),
            (
                "Use safe water and raw materials | PDF page 21; printed 20",
                "Use water known to be safe or treated to make it safe. Choose fresh foods and safety-processed ingredients, wash produce, and respect expiry dates. Microbial disinfection does not remove harmful chemicals.",
            ),
        ],
    ),
    (
        "infant-feeding",
        "Infant and young child feeding — WHO fact sheet (2026 update)",
        "https://www.who.int/news-room/fact-sheets/detail/infant-and-young-child-feeding",
        "2026-08-04",
        "infant-feeding.html",
        [
            (
                "Breastfeeding support | HTML heading Breastfeeding; snapshot 2026-11-20",
                "Support mothers to feed responsively, day and night, and to start breastfeeding within the first hour after birth with immediate skin-to-skin contact. Keep mother and baby together around the clock. Additional food or drink, including water, is avoided unless medically necessary. Offer counselling across antenatal and postnatal contacts and community support.",
            ),
            (
                "Complementary feeding frequency and responsive feeding | HTML heading Complementary feeding; snapshot 2026-11-20",
                "Complementary foods start around six months, initially in small quantities, with progressively greater amounts, texture and variety. Continue frequent breastfeeding until two years or longer. Respond to hunger and fullness cues and handle food hygienically. Offer 2–3 meals daily at 6–8 months and 3–4 at 9–23 months, plus 1–2 snacks when needed. During illness, increase fluids and breastfeeding and offer soft preferred foods.",
            ),
        ],
    ),
]
catalog = []
for id, title, url, date, file, parts in items:
    text = (
        "# "
        + title
        + "\n\n"
        + "\n\n".join("## " + h + "\n\n" + t for h, t in parts)
        + "\n"
    )
    (out / (id + ".md")).write_text(text)
    meta = {
        "url": url,
        "title": title,
        "organization": "World Health Organization",
        "language": "en",
        "topic": "Infant feeding and caregiver food hygiene",
        "published_at": date,
        "reuse_note": "Agent-written English paraphrase of selected WHO passages, checked against official HTML or rendered PDF. Not verbatim WHO text; not WHO-endorsed or clinically reviewed. Original copyright retained; no CC licence asserted. Local noncommercial thesis research, not an open-data redistribution grant.",
    }
    (out / (id + ".metadata.json")).write_text(
        json.dumps(meta, ensure_ascii=False, indent=2)
    )
    catalog.append(
        dict(
            id=id,
            **meta,
            raw_file=str((raw / file).relative_to(r)),
            raw_sha256=hashlib.sha256((raw / file).read_bytes()).hexdigest(),
            prepared_sha256=hashlib.sha256(text.encode()).hexdigest(),
            selected_sections=[h for h, t in parts],
            preparation="Source-grounded paraphrase; PDF pages visually inspected because extraction was incomplete",
            license="PDF page 3: all rights reserved"
            if id == "five-keys"
            else "WHO website copyright; no CC assertion",
            status="prepared",
        )
    )
c = r / "data/sources/who/2026-11-20"
c.mkdir(parents=True, exist_ok=True)
(c / "catalog.json").write_text(
    json.dumps(
        {"batch": "2026-11-20", "sources": catalog}, ensure_ascii=False, indent=2
    )
)
