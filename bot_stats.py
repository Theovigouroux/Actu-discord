"""Bot 3 : statistique de sensibilisation toutes les heures.
Uniquement des chiffres PUBLIÉS par des organismes officiels (aucun calcul maison)."""
import os
import time
import requests
import feedparser
from common import *

WEBHOOK = os.environ["WEBHOOK_STATS"]
UA = {"User-Agent": "Mozilla/5.0"}

# Domaines considérés comme officiels pour les recherches web
DOMAINES_OFFICIELS = (
    "gouv.fr", "santepubliquefrance.fr", "insee.fr", "who.int", "un.org", "unicef.org", "iom.int",
    "europa.eu", "worldbank.org", "unhcr.org", "unwomen.org", "fao.org", "oecd.org", "ofdt.fr",
    "euda.europa.eu", "eea.europa.eu", "fondationpourlelogement.fr", "ined.fr", "senat.fr",
    "assemblee-nationale.fr", "data.gouv.fr", "unodc.org", "undp.org", "wfp.org",
)


# ---------- Données officielles via API ----------
def wb(pays, indicateur):
    """Dernière valeur PUBLIÉE d'un indicateur de la Banque mondiale (données OMS/ONU/FAO...)."""
    r = requests.get(f"https://api.worldbank.org/v2/country/{pays}/indicator/{indicateur}",
                     params={"format": "json", "mrnev": 1}, timeout=30)
    r.raise_for_status()
    d = r.json()[1][0]
    return float(d["value"]), d["date"]


def officiel_wb(titre, indicateur, fmt, detail, organisme="Banque mondiale (données officielles OMS/ONU)"):
    def collecteur():
        v, an = wb("WLD", indicateur)
        return {
            "titre": titre, "chiffre": fmt(v), "faits": [detail, f"Année de la donnée : {an}"],
            "source": organisme, "url": f"https://data.worldbank.org/indicator/{indicateur}",
            "note": f"📊 Donnée officielle publiée ({an})",
        }
    collecteur.__name__ = indicateur
    return collecteur


COLLECTEURS_WB = [
    officiel_wb("Sécurité routière dans le monde", "SH.STA.TRAF.P5",
                lambda v: f"{v:.1f} morts pour 100 000 habitants", "Taux de mortalité routière mondial, par an."),
    officiel_wb("Suicide dans le monde", "SH.STA.SUIC.P5",
                lambda v: f"{v:.1f} décès pour 100 000 habitants",
                "Taux de mortalité par suicide mondial, par an. En France, le 3114 est le numéro national de prévention (gratuit, 24h/24)."),
    officiel_wb("Mortalité des enfants de moins de 5 ans", "SH.DYN.MORT",
                lambda v: f"{v:.1f} décès pour 1 000 naissances vivantes", "Taux de mortalité des moins de 5 ans dans le monde."),
    officiel_wb("Faim dans le monde", "SN.ITK.DEFC.ZS",
                lambda v: f"{v:.1f} % de la population mondiale", "Part de la population en sous-alimentation chronique."),
    officiel_wb("Extrême pauvreté", "SI.POV.DDAY",
                lambda v: f"{v:.1f} % de la population mondiale", "Part de la population sous le seuil international d'extrême pauvreté."),
    officiel_wb("Mortalité maternelle", "SH.STA.MMRT",
                lambda v: f"{v:.0f} décès pour 100 000 naissances vivantes", "Décès de femmes liés à la grossesse ou à l'accouchement."),
    officiel_wb("Tuberculose", "SH.TBS.INCD",
                lambda v: f"{v:.0f} nouveaux cas pour 100 000 habitants", "Incidence mondiale de la tuberculose, par an."),
    officiel_wb("Réfugiés dans le monde", "SM.POP.REFG",
                lambda v: f"{v/1e6:.1f} millions de réfugiés", "Personnes ayant fui leur pays (données HCR/UNHCR).",
                "Banque mondiale (données officielles UNHCR)"),
    officiel_wb("Enfants non scolarisés", "SE.PRM.UNER",
                lambda v: f"{v/1e6:.0f} millions d'enfants", "Enfants en âge d'école primaire qui ne sont pas scolarisés (données UNESCO).",
                "Banque mondiale (données officielles UNESCO)"),
]


# ---------- Données officielles en TEMPS RÉEL ----------
def c_seismes():
    r = requests.get("https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_day.geojson", timeout=30)
    r.raise_for_status()
    f = r.json()["features"]
    if not f:
        raise ValueError("aucun séisme")
    fort = max(f, key=lambda x: x["properties"]["mag"] or 0)["properties"]
    return {
        "titre": "Séismes des dernières 24 h", "chiffre": f"{len(f)} séismes de magnitude ≥ 4,5",
        "faits": [f"Le plus fort : magnitude {fort['mag']} — {fort['place']}"],
        "source": "USGS (Service géologique américain)", "url": "https://earthquake.usgs.gov/earthquakes/map/",
        "note": "📡 Officiel, temps réel",
    }


def c_co2():
    txt = requests.get("https://gml.noaa.gov/webdata/ccgg/trends/co2/co2_daily_mlo.txt", timeout=30, headers=UA).text
    lignes = [l.split() for l in txt.splitlines() if l.strip() and not l.startswith("#")]
    valides = [l for l in lignes if float(l[4]) > 0]
    a, m, j, _, ppm = valides[-1][:5]
    return {
        "titre": "CO₂ dans l'atmosphère", "chiffre": f"{ppm} ppm",
        "faits": [f"Dernière mesure quotidienne à l'observatoire de Mauna Loa : {j}/{m}/{a}",
                  "Niveau préindustriel (avant 1750) : environ 280 ppm"],
        "source": "NOAA Global Monitoring Laboratory", "url": "https://gml.noaa.gov/ccgg/trends/",
        "note": "📡 Officiel, mesure quotidienne",
    }


def c_oms_alerte():
    e = feedparser.parse("https://www.who.int/feeds/entity/don/en/rss.xml", agent="Mozilla/5.0").entries
    if not e:
        raise ValueError("flux OMS vide")
    e = e[0]
    return {
        "titre": "Dernière alerte sanitaire de l'OMS", "chiffre": clean(e.title),
        "faits": [clean(e.get("summary"))[:800]],
        "source": "OMS — Disease Outbreak News", "url": e.link,
        "note": "📡 Officiel, publié par l'OMS",
    }


COLLECTEURS_API = COLLECTEURS_WB + [c_seismes, c_co2, c_oms_alerte]


# ---------- Recherche web : chiffres officiels uniquement ----------
SUJETS_RECHERCHE = [
    "nombre de femmes tuées par leur conjoint ou ex-conjoint (féminicides conjugaux) en France, dernier bilan officiel",
    "violences conjugales et sexuelles en France, dernières statistiques officielles",
    "mortalité routière en France, dernier bilan de la Sécurité routière",
    "décès liés au tabac en France, Santé publique France",
    "décès liés à l'alcool en France, Santé publique France",
    "harcèlement scolaire en France, ministère de l'Éducation nationale",
    "personnes sans domicile en France, INSEE ou Fondation pour le logement",
    "migrants morts ou disparus depuis le début de l'année, Projet Missing Migrants de l'OIM",
    "décès attribuables à la pollution de l'air en France, Santé publique France",
    "décès liés aux drogues en Europe, Agence de l'Union européenne sur les drogues",
    "mariages d'enfants dans le monde, UNICEF",
    "violences faites aux femmes dans le monde, OMS ou ONU Femmes",
]


def recherche(sujet):
    prompt = f"""Cherche sur le web le chiffre officiel le PLUS RÉCENT publié sur : {sujet}.
N'utilise que le site officiel de l'organisme (ministère, Santé publique France, INSEE, OMS, ONU, UNICEF, OIM, UE...). Ne fais AUCUN calcul : recopie le chiffre tel que publié.
Réponds uniquement avec ce JSON :
{{"titre":"titre court","chiffre":"le chiffre tel que publié, avec son unité","texte":"2 phrases factuelles et neutres","annee":"année ou date de publication","organisme":"nom de l'organisme","definitions":{{"terme technique ou complexe utilisé":"définition simple"}}}}
Si tu ne trouves pas de chiffre officiel daté, réponds {{"erreur":"introuvable"}}."""
    texte, meta = gemini(prompt, system="Tu es un assistant de vérification factuelle, strictement neutre. N'invente jamais un chiffre.", search=True)
    d = parse_json(texte)
    if "erreur" in d:
        raise ValueError("introuvable")
    liens = []
    for c in meta.get("groundingChunks", []):
        w = c.get("web")
        if w and any(w.get("title", "").lower().endswith(dom) for dom in DOMAINES_OFFICIELS):
            liens.append((w["title"], w["uri"]))
    if not liens:
        raise ValueError("aucune source officielle")
    d["liens"] = liens[:4]
    return d


# ---------- Mise en forme ----------
def definitions_champ(defs):
    if not defs:
        return []
    return [{"name": "📖 Définitions", "value": "\n".join(f"**{k}** : {v}" for k, v in defs.items())[:1000]}]


def rediger(c):
    prompt = f"""Données officielles :
Titre : {c['titre']}
Chiffre clé : {c['chiffre']}
Détails : {'; '.join(c['faits'])}

Rédige 2 phrases neutres de sensibilisation. N'utilise AUCUN chiffre autre que ceux fournis, et ne fais aucun calcul.
Liste dans "definitions" chaque terme technique ou complexe utilisé (ex. espérance de vie, incidence, sous-alimentation, magnitude, ppm, mortalité maternelle...) avec une définition simple.
Réponds en JSON : {{"texte":"...","definitions":{{"terme":"définition"}}}}"""
    texte, _ = gemini(prompt, system=REGLES_NEUTRALITE, json_out=True)
    return parse_json(texte)


def embed_api(c):
    r = rediger(c)
    champs = definitions_champ(r.get("definitions"))
    champs.append({"name": "📎 Source officielle", "value": f"[{c['source']}]({c['url']})"})
    return {"title": f"⚠️ {c['titre']}", "description": f"# {c['chiffre']}\n{r['texte']}",
            "color": 0xE74C3C, "fields": champs,
            "footer": {"text": f"{c['note']} • Chiffre publié tel quel, texte rédigé par IA"}}


def embed_recherche(d):
    champs = definitions_champ(d.get("definitions"))
    liens = " • ".join(f"[{t[:40]}]({u})" for t, u in d["liens"])[:1000]
    champs.append({"name": f"📎 Sources officielles — {d.get('organisme', '')}", "value": liens})
    return {"title": f"⚠️ {d['titre']}", "description": f"# {d['chiffre']}\n{d['texte']}",
            "color": 0xE74C3C, "fields": champs,
            "footer": {"text": f"📊 Donnée officielle publiée ({d.get('annee', '?')}) • Vérifie via les sources"}}


def main():
    sources = [("api", f) for f in COLLECTEURS_API] + [("web", s) for s in SUJETS_RECHERCHE]
    n = len(sources)
    debut = int(time.time() // 3600) % n
    for k in range(n):  # si une source échoue, on passe à la suivante
        genre, s = sources[(debut + k) % n]
        try:
            embed = embed_api(s()) if genre == "api" else embed_recherche(recherche(s))
        except Exception as e:
            print(f"[stat ignorée] {getattr(s, '__name__', s)}: {e}")
            continue
        post_discord(WEBHOOK, "Le saviez-vous ?", "", [embed])
        return
    print("Aucune stat disponible cette heure-ci")


if __name__ == "__main__":
    main()
