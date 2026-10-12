"""Fonctions partagées : Gemini, flux RSS, Discord."""
import os
import re
import json
import time
import requests
import feedparser
from calendar import timegm
from datetime import datetime, timezone, timedelta

MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

REGLES_NEUTRALITE = """Tu es un rédacteur de synthèse factuel et strictement neutre.
Règles :
- Utilise UNIQUEMENT les informations fournies. N'invente rien, n'ajoute aucun chiffre ni détail extérieur.
- Pas d'adjectifs émotionnels, pas d'opinion, pas de jugement, pas de vocabulaire militant.
- Attribue les affirmations contestées ("selon X", "d'après Y").
- Si les sources divergent, mentionne-le explicitement.
- Privilégie les événements couverts par plusieurs médias différents.
- Écris en français clair."""


# ---------- Gemini ----------
def gemini(prompt, system=None, json_out=False, search=False):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 8192},
    }
    if system:
        body["systemInstruction"] = {"parts": [{"text": system}]}
    if search:
        body["tools"] = [{"google_search": {}}]
    else:
        body["generationConfig"]["thinkingConfig"] = {"thinkingBudget": 0}
        if json_out:
            body["generationConfig"]["responseMimeType"] = "application/json"
    headers = {"x-goog-api-key": os.environ["GEMINI_API_KEY"]}

    for tentative in range(4):
        r = requests.post(url, json=body, headers=headers, timeout=120)
        if r.status_code in (429, 500, 503):
            time.sleep(10 * (tentative + 1))
            continue
        r.raise_for_status()
        cand = r.json()["candidates"][0]
        texte = "".join(p.get("text", "") for p in cand["content"]["parts"])
        return texte, cand.get("groundingMetadata", {})
    raise RuntimeError("Gemini indisponible après plusieurs tentatives")


def parse_json(texte):
    texte = texte.strip()
    texte = re.sub(r"^```(?:json)?|```$", "", texte, flags=re.M).strip()
    try:
        return json.loads(texte)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", texte, flags=re.S)
        if not m:
            raise
        return json.loads(m.group(0))


# ---------- RSS ----------
def clean(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html or "")).strip()


def fetch_articles(feeds, max_age_hours=24, per_feed=10):
    limite = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
    out, vus = [], set()
    for nom, url in feeds.items():
        try:
            entries = feedparser.parse(url, agent="Mozilla/5.0").entries
        except Exception as e:
            print(f"[flux ignoré] {nom}: {e}")
            continue
        n = 0
        for e in entries:
            link, titre = e.get("link"), clean(e.get("title"))
            if not link or not titre or link in vus:
                continue
            t = e.get("published_parsed") or e.get("updated_parsed")
            pub = datetime.fromtimestamp(timegm(t), timezone.utc) if t else None
            if pub and pub < limite:
                continue
            vus.add(link)
            out.append({"source": nom, "title": titre, "summary": clean(e.get("summary"))[:350],
                        "link": link, "published": pub})
            n += 1
            if n >= per_feed:
                break
        print(f"[flux] {nom}: {n} article(s)")
    return out


def articles_pour_prompt(arts):
    return "\n".join(f"[{i}] ({a['source']}) {a['title']} — {a['summary']}" for i, a in enumerate(arts))


def histoires_en_embeds(histoires, arts, couleur):
    """Transforme les histoires résumées par Gemini en embeds Discord avec sources cliquables."""
    embeds = []
    for h in histoires:
        ids = [i for i in h.get("sources", []) if isinstance(i, int) and 0 <= i < len(arts)]
        par_media = {}
        for i in ids:
            par_media.setdefault(arts[i]["source"], arts[i]["link"])
        if not par_media:
            continue  # pas de source = on ne publie pas
        liens, total = [], 0
        for nom, lien in par_media.items():
            md = f"[{nom}]({lien})"
            if total + len(md) > 950:
                break
            liens.append(md)
            total += len(md) + 3
        embeds.append({
            "title": h["titre"][:250],
            "description": h["resume"][:3500],
            "color": couleur,
            "fields": [{"name": f"📎 Sources ({len(liens)})", "value": " • ".join(liens)}],
        })
    return embeds


# ---------- Discord ----------
def post_discord(webhook, username, content, embeds):
    for i in range(0, max(len(embeds), 1), 4):
        payload = {"username": username, "embeds": embeds[i:i + 4]}
        if i == 0 and content:
            payload["content"] = content
        r = requests.post(webhook, json=payload, timeout=30)
        if r.status_code == 429:
            time.sleep(float(r.json().get("retry_after", 2)) + 0.5)
            r = requests.post(webhook, json=payload, timeout=30)
        r.raise_for_status()
        time.sleep(1)
