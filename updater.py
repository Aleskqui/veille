import os
import json
from datetime import datetime
import feedparser
import google.generativeai as genai

# 1. Configuration de l'authentification
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY") or os.environ.get("API_VEILLE")
if not GEMINI_API_KEY:
    raise ValueError("Clé API introuvable dans les variables d'environnement.")

genai.configure(api_key=GEMINI_API_KEY)

# 2. Définition du modèle Gemini 2.5 Flash
try:
    model = genai.GenerativeModel("gemini-2.5-flash")
except Exception:
    model = genai.GenerativeModel("models/gemini-2.5-flash")

# 3. Flux RSS ciblés
FEEDS = {
    "ia": [
        "https://www.technologyreview.com/feed/",
        "https://feeds.feedburner.com/venturebeat/ai"
    ],
    "sport": [
        "https://theanalyst.com/feed/",
        "https://trainingground.guru/articles?format=feed&type=rss"
    ],
    "demat": [
        "https://www.archimag.com/rss.xml",
        "https://www.lemondeinformatique.fr/flux-rss/thematique/gestion-documentaire/rss.xml"
    ]
}

def fetch_recent_articles(urls, max_items=5):
    articles = []
    for url in urls:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:max_items]:
                articles.append({
                    "title": entry.get("title", ""),
                    "summary": entry.get("summary", entry.get("description", ""))[:400],
                    "link": entry.get("link", ""),
                    "source": feed.feed.get("title", "Média web")
                })
        except Exception as err:
            print(f"Erreur lors de la lecture du flux {url}: {err}")
    return articles

def generate_topic_synthesis(topic_key, topic_label, articles):
    context = ""
    for idx, a in enumerate(articles[:5], 1):
        context += f"Source {idx} ({a['source']}) : {a['title']}\nRésumé : {a['summary']}\nLien : {a['link']}\n\n"

    prompt = f"""
Tu es un analyste expert de haut niveau. Ta mission est de rédiger la fiche de veille hebdomadaire du lundi pour la thématique : "{topic_label}".
Voici les données collectées récemment :
{context}

Rédige une synthèse critique en français. Ne retiens QUE les informations majeures à ne pas louper.
Réponds STRICTEMENT avec un objet JSON respectant cette structure exacte, sans texte avant ni après :
{{
  "title": "Titre percutant et professionnel",
  "highlight": "En 1 ou 2 phrases, l'information capitale absolue à ne pas rater cette semaine.",
  "analysis": "Analyse de fond détaillée en 2 paragraphes sur les enjeux concrets.",
  "keyPoints": [
    "Point marquant 1 (chiffre, fait vérifié ou décision)",
    "Point marquant 2",
    "Point marquant 3"
  ],
  "impact": "Impact métier concret pour une entreprise ou une alternance.",
  "sources": [
    {{ "name": "Nom de la source", "url": "URL du lien", "type": "Type d'organisme" }}
  ]
}}
"""
    try:
        response = model.generate_content(
            prompt,
            generation_config={"response_mime_type": "application/json"}
        )
        data = json.loads(response.text)
    except Exception:
        response = model.generate_content(prompt)
        text = response.text.strip()
        if text.startswith("```json"):
            text = text[7:-3].strip()
        elif text.startswith("```"):
            text = text[3:-3].strip()
        data = json.loads(text)

    data["id"] = f"{topic_key}-{datetime.now().strftime('%Y%m%d')}"
    data["topic"] = topic_key
    data["topicLabel"] = topic_label
    data["datePublished"] = datetime.now().strftime("%d/%m/%Y")
    return data

def main():
    today = datetime.now()
    edition_id = today.strftime("%Y-W%W")
    edition_label = f"Lundi {today.strftime('%d/%m/%Y')}"

    print(f"Lancement de la veille pour l'édition {edition_id} avec Gemini 2.5 Flash...")

    topics_data = []
    for key, label in [("ia", "Avancées de l'IA"), ("sport", "Data dans le Sport"), ("demat", "Dématérialisation")]:
        articles = fetch_recent_articles(FEEDS[key])
        if articles:
            synth = generate_topic_synthesis(key, label, articles)
            topics_data.append(synth)

    new_edition = {
        "id": edition_id,
        "date": today.strftime("%Y-%m-%d"),
        "label": edition_label,
        "editorial": f"Synthèse automatique consolidée du {edition_label}. Couverture complète des signaux forts en IA, data sportive et dématérialisation.",
        "topics": topics_data
    }

    editions_file = "editions.json"
    editions = []
    if os.path.exists(editions_file):
        try:
            with open(editions_file, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    editions = json.loads(content)
        except Exception as e:
            print(f"Lecture editions.json : {e}")
            editions = []

    editions = [e for e in editions if e.get("id") != edition_id]
    editions.insert(0, new_edition)

    with open(editions_file, "w", encoding="utf-8") as f:
        json.dump(editions, f, indent=2, ensure_ascii=False)

    print("Veille mise à jour avec succès dans editions.json.")

if __name__ == "__main__":
    main()
