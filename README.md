# Bots Discord : actu + stats (webhooks + GitHub Actions + Gemini)

## Mise en place
1. **Discord** : crée un webhook par bot (Paramètres du salon > Intégrations > Webhooks). Chaque webhook peut être dans un serveur différent.
2. **Gemini** : clé gratuite sur https://aistudio.google.com/apikey
3. **GitHub** : crée un repo privé, uploade tous les fichiers (garde `.github/workflows`).
4. Repo > Settings > Secrets and variables > Actions > New repository secret :
   - `GEMINI_API_KEY`
   - `WEBHOOK_ACTU_JOUR` (serveur 1)
   - `WEBHOOK_ACTU_HEURE` (serveur 2)
   - `WEBHOOK_STATS` (serveur 3)
5. Repo > Settings > Actions > General > Workflow permissions : "Read and write permissions".
6. Onglet Actions : lance chaque workflow à la main (Run workflow) pour tester.

## Comment ça marche
- **Actu du jour** : lit ~14 flux RSS de médias différents, Gemini regroupe par événement et résume de façon neutre, les sources cliquables sont ajoutées sous chaque info.
- **Actu monde live** : toutes les heures, uniquement les nouveaux articles (mémorisés dans `seen.json`).
- **Stats** : chaque heure, un chiffre officiel publié tel quel (Banque mondiale/OMS/ONU/UNHCR/UNESCO, USGS, NOAA, alertes OMS) ou trouvé sur le site d'un organisme officiel (ministères, Santé publique France, OIM, UNICEF...). Aucun calcul maison. Pas de source officielle = pas de publication.

## Limites
- Les heures cron sont en UTC, GitHub peut avoir quelques minutes de retard.
- Certains flux RSS peuvent changer d'adresse : les flux cassés sont simplement ignorés (voir les logs dans Actions).
- Il n'existe pas de compteur officiel en direct pour la plupart des décès : les organismes publient chaque année ou chaque mois. Le bot affiche le dernier chiffre publié avec son année. Seuls les séismes (USGS), le CO₂ (NOAA) et les alertes de l'OMS sont en temps réel.
- Un résumé IA peut se tromper : les sources sont là pour vérifier.
