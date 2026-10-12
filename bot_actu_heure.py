"""Bot 2 : actu mondiale mise à jour toutes les heures (nouveaux articles seulement)."""
import os
import json
from datetime import datetime
from zoneinfo import ZoneInfo
from common import *
from bot_actu_jour import FLUX_MONDE

WEBHOOK = os.environ["WEBHOOK_ACTU_HEURE"]
STATE = "seen.json"


def charger():
    try:
        with open(STATE, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def main():
    deja = set(charger())
    arts = [a for a in fetch_articles(FLUX_MONDE, 3, 8) if a["link"] not in deja]
    print(f"{len(arts)} nouvel(le)s article(s)")

    if len(arts) >= 2:
        prompt = f"""Voici de NOUVEAUX articles internationaux, numérotés :
{articles_pour_prompt(arts)}

Regroupe-les par événement et garde les 5 plus importants. Pour chacun, rédige un résumé neutre de 2 à 3 phrases.
Réponds en JSON : {{"histoires":[{{"titre":"titre factuel","resume":"...","sources":[numéros des articles utilisés]}}]}}"""
        texte, _ = gemini(prompt, system=REGLES_NEUTRALITE, json_out=True)
        embeds = histoires_en_embeds(parse_json(texte)["histoires"], arts, 0xE67E22)
        if embeds:
            heure = datetime.now(ZoneInfo("Europe/Paris")).strftime("%Hh%M")
            post_discord(WEBHOOK, "Actu Monde (live)", f"🔄 **Mise à jour de l'actu mondiale — {heure}**", embeds)

    tous = [a["link"] for a in arts] + list(deja)
    with open(STATE, "w", encoding="utf-8") as f:
        json.dump(tous[:1000], f)


if __name__ == "__main__":
    main()
