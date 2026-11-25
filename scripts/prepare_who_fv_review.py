"""Prepare selected review evidence, preserving its uncertainty; no DB mutations."""
import hashlib
import json
import re
from pathlib import Path
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
ID = 'fruits-vegetables-nuts-pulses-seeds-review'
raw = ROOT / 'data/raw/who/2026-10-27' / f'{ID}.pdf'
out = ROOT / 'data/processed/who/2026-10-27'
out.mkdir(parents=True, exist_ok=True)
reader = PdfReader(raw)
pages = []
for page in reader.pages:
    lines = (page.extract_text() or '').splitlines()
    lines = [line.strip() for i, line in enumerate(lines) if not (i < 2 and line.strip().isdigit())]
    pages.append(re.sub(r'\s+', ' ', ' '.join(lines)).strip())
def between(page, start, end=None):
    text = pages[page-1]
    assert text.count(start) == 1, start
    text = text[text.index(start):]
    if end:
        assert text.count(end) == 1, end
        text = text[:text.index(end)]
    assert len(text) > 50 and '\ufffd' not in text
    return text.strip()
certainty = between(4, 'Certainty of evidence:', 'Key results:')
sections = [
    ('Eligibility and synthesis limitations', '3', between(3, 'Selection Criteria', 'Results')),
    ('Study characteristics and certainty', '3–4', between(3, 'Study characteristics:') + ' ' + certainty),
    ('Authors conclusions and certainty', '4', certainty + ' ' + between(4, 'Author’s conclusions')),
    ('Implications for practice and policy', '44 (printed 14)', between(44, 'Implications for Practice and Policy', 'Implications for Research')),
]
title = 'Systematic review: fruits, vegetables, pulses, nuts and seeds in children 6–23 months (Harrison et al.; WHO-hosted)'
url = 'https://cdn.who.int/media/docs/default-source/nutrition-and-food-safety/complementary-feeding/cf-guidelines/systematic-review-fruits-and-vegetables-and-nuts-pulses-and-seeds.pdf'
text = []
for heading, loc, body in sections:
    text += [f'## {title} — {heading} | PDF pages {loc}', '', body, '']
(out/f'{ID}.md').write_text('\n'.join(text), encoding='utf-8')
metadata = dict(url=url,title=title,organization='Centre for Global Child Health, The Hospital for Sick Children; hosted by WHO',language='en',topic='Systematic review evidence and uncertainty: fruits, vegetables, pulses, nuts and seeds; children 6–23 months',reuse_note='User-selected PDF for private local thesis research. No explicit Creative Commons licence located in PDF; do not label as CC-licensed or redistribute this text as open data. Authors: Harrison, Oh, Charbonneau, Owais, Keats and Bhutta. Selected source text; formatting and section headings adapted. This is a systematic review, not a WHO recommendation. Clinical validation not performed.',published_at=None,updated_at=None)
(out/f'{ID}.metadata.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n')
manifest = dict(id=ID,url=url,pdf_sha256=hashlib.sha256(raw.read_bytes()).hexdigest(),pdf_pages=len(reader.pages),selected_pdf_pages=[3,4,44],role='systematic_review',publication_date=None,license='No explicit licence located; no open-licence claim',sections=[dict(name=h,pdf_pages=l) for h,l,_ in sections],exclusions='Detailed effect tables, background recommendations, references and appendices not indexed. Selected synthesis retains observational design and very low certainty.',prepared_sha256=hashlib.sha256((out/f'{ID}.md').read_bytes()).hexdigest())
(ROOT/'data/sources/who/2026-10-27'/f'{ID}.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
print('Prepared',len(sections),'sections from',len(reader.pages),'PDF pages')
