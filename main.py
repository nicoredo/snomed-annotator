
import re
import os
import asyncio
from typing import List, Dict, Any
from fastapi import FastAPI, Body
from fastapi.middleware.cors import CORSMiddleware
import httpx

app = FastAPI(title="SNOMED Annotator (demo)",
              description="Annotates Spanish clinical text with SNOMED CT concept matches using Snowstorm demo API. Not for production.",
              version="0.2.0")

# CORS: allow all (you can restrict to your domain later)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SNOWSTORM_BASE = os.getenv("SNOWSTORM_BASE", "https://snowstorm.snomedtools.org")
ACCEPT_LANGUAGE = os.getenv("ACCEPT_LANGUAGE", "es")

STOPWORDS = set("""de del la el los las y o en con sin por para un una al actual previa previo
antecedente antecedentes paciente pacientes la el lo a ante bajo cabe con contra de desde en entre hacia hasta para por
segun seg\u00fan sin so sobre tras y e ni o u que""".split())

TOKEN_RE = re.compile(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9]+", re.UNICODE)

def normalize(s: str) -> str:
    # Lowercase and strip diacritics for candidate generation
    import unicodedata
    s = s.lower()
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")

def tokens(text: str) -> List[str]:
    return TOKEN_RE.findall(text)

def ngrams(tok: List[str], n: int) -> List[str]:
    out = []
    for i in range(len(tok) - n + 1):
        out.append(" ".join(tok[i:i+n]))
    return out

def candidate_terms(text: str, max_candidates: int = 60) -> List[str]:
    tks = tokens(text)
    # keep original-cased tokens, but filter using normalized stopwords
    norm_map = [normalize(t) for t in tks]
    uni = [t for t, n in zip(tks, norm_map) if len(n) >= 4 and n not in STOPWORDS]
    bi = ngrams(tks, 2)
    tri = ngrams(tks, 3)
    # filter bi/tri to contain at least one non-stopword token of len>=4 (normalized)
    def keep(seq):
        kept = []
        for s in seq:
            nm = [normalize(x) for x in s.split()]
            if any(len(x) >= 4 and x not in STOPWORDS for x in nm):
                kept.append(s)
        return kept
    bi = keep(bi)
    tri = keep(tri)
    # de-duplicate while preserving order
    seen = set()
    out = []
    for s in uni + bi + tri:
        k = normalize(s)
        if k not in seen:
            seen.add(k)
            out.append(s)
        if len(out) >= max_candidates:
            break
    return out

async def snowstorm_search(term: str, client: httpx.AsyncClient) -> List[Dict[str, Any]]:
    # Native Snowstorm descriptions endpoint (browser variant)
    url = f"{SNOWSTORM_BASE}/snowstorm/snomed-ct/v2/descriptions"
    params = {
        "active": "true",
        "conceptActive": "true",
        "groupByConcept": "true",
        "searchMode": "STANDARD",
        "term": term,
        "limit": "5",
    }
    headers = {"Accept-Language": ACCEPT_LANGUAGE}
    r = await client.get(url, params=params, headers=headers, timeout=15.0)
    r.raise_for_status()
    data = r.json()
    items = data.get("items") or data.get("matches") or []
    results = []
    for it in items:
        concept = it.get("concept") or {}
        results.append({
            "term": it.get("term"),
            "conceptId": concept.get("conceptId"),
            "fsn": (concept.get("fsn") or {}).get("term"),
            "semanticTag": (concept.get("fsn") or {}).get("semanticTag"),
        })
    return results

def find_offsets(raw: str, term: str) -> List[Dict[str, int]]:
    # Case-insensitive, accent-sensitive simple search
    if not term:
        return []
    offs = []
    pattern = re.compile(re.escape(term), re.IGNORECASE)
    for m in pattern.finditer(raw):
        offs.append({"start": m.start(), "end": m.end()})
    return offs

@app.get("/healthz")
async def healthz():
    return {"ok": True, "snowstorm": SNOWSTORM_BASE, "lang": ACCEPT_LANGUAGE}

@app.post("/annotate")
async def annotate(payload: Dict[str, Any] = Body(..., example={"text":"Paciente con infarto agudo de miocardio y fibrilación auricular. PA 150/95 mmHg."})):
    raw = payload.get("text") or ""
    if not raw.strip():
        return {"matches": [], "candidates": [], "note": "Empty text"}
    max_candidates = int(payload.get("max_candidates", 60))
    lang = payload.get("lang") or ACCEPT_LANGUAGE

    cand = candidate_terms(raw, max_candidates=max_candidates)

    results = []
    async with httpx.AsyncClient() as client:
        tasks = [snowstorm_search(term, client) for term in cand]
        batches = await asyncio.gather(*tasks, return_exceptions=True)
        for term, res in zip(cand, batches):
            if isinstance(res, Exception):
                continue
            for hit in res:
                # require we can actually see the returned term in raw text
                offsets = find_offsets(raw, hit.get("term") or "")
                if offsets:
                    results.append({
                        "match": hit.get("term"),
                        "conceptId": hit.get("conceptId"),
                        "fsn": hit.get("fsn"),
                        "semanticTag": hit.get("semanticTag"),
                        "offsets": offsets
                    })

    # de-duplicate by (conceptId, match)
    seen = set()
    uniq = []
    for r in results:
        k = (r["conceptId"], r["match"].lower())
        if k in seen:
            continue
        seen.add(k)
        uniq.append(r)

    return {
        "matches": uniq,
        "candidates": cand[:max_candidates],
        "lang": lang,
        "source": SNOWSTORM_BASE,
        "disclaimer": "Demo only. Uses public Snowstorm; for production, host your own Snowstorm and set SNOWSTORM_BASE."
    }

# Optional: simple GET for quick manual testing
@app.get("/annotate")
async def annotate_get(q: str):
    return await annotate({"text": q})
