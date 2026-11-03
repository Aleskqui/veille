import os
import json
import urllib.request
from datetime import datetime
import feedparser
import google.generativeai as genai

# Configuration de la clé API
api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("API_VEILLE")
if not api_key:
    raise ValueError("Clé API introuvable.")

genai.configure(api_key=api_key)
model = genai.GenerativeModel("gemini-1.5-flash")

# Flux RSS sélectionnés (avec sources stables)
FEEDS = {
    "ia": [
        "https://feeds.feedburner.com/venturebeat/ai",
        "https://techcrunch.com/category/artificial-intelligence/feed/"
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

def fetch_recent_articles(urls, max_items=4):
    articles = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

    for url in urls:
        print(f"--> Récupération du flux : {url}")
        try:
            req = urllib.request.Request(url, headers=headers)
            # Timeout strict de 8 secondes par flux pour ne jamais bloquer
            with urllib.request.urlopen(req, timeout=8) as response:
                content = response.read()
                feed = feedparser.parse(content)
                for entry in feed.entries[:max_items]:
                    articles.append({
                        "title": entry.get("title", ""),
                        "summary": entry.get("summary", entry.get("description", ""))[:300],
                        "link": entry.get("link", "#"),
                        "source": feed.feed.get("title", "Média spécialisé")
                    })
                print(f"    OK ({len(feed.entries)} articles trouvés)")
        except Exception as e:
            print(f"    Échec/Délai dépassé pour {url} ({e}) -> passage à la suite")
            continue

    return articles

def generate_topic_synthesis(topic_key, topic_label, articles):
    print(f"--> Génération de la synthèse IA pour : {topic_label}")
    context = ""
    for idx, a in enumerate(articles[:4], 1):
        context += f"Source {idx} ({a['source']}) : {a['title']}\nRésumé : {a['summary']}\nLien : {a['link']}\n\n"

    # Si aucun flux n'a répondu, on génère une fiche basée sur les grandes tendances de la semaine
    if not context.strip():
        context = f"Actualité récente et enjeux majeurs du moment concernant {topic_label}."

    prompt = f"""
Tu es un analyste expert de haut niveau. Rédige la fiche de veille stratégique pour : "{topic_label}".
Voici les éléments d'actualité récents :
{context}

Rédige une synthèse critique en français avec les informations capitales.
Réponds STRICTEMENT avec un objet JSON sans aucun formatage Markdown autour, selon cette structure exacte :
{{
  "title": "Titre professionnel et percutant",
  "highlight": "En 1 ou 2 phrases, l'information capitale absolue à ne pas rater.",
  "analysis": "Analyse de fond détaillée en 2 paragraphes sur les enjeux.",
  "keyPoints": [
    "Point marquant 1 (chiffre ou fait vérifié)",
    "Point marquant 2",
    "Point marquant 3"
  ],
  "impact": "Impact métier concret pour une entreprise ou alternance.",
  "sources": [
    {{ "name": "Nom de la source", "url": "https://exemple.com", "type": "Presse / Rapport" }}
  ]
}}
"""
    try:
        response = model.generate_content(
            prompt,
            generation_config={"response_mime_type": "application/json"}
        )
        data = json.loads(response.text)
    except Exception as e:
        print(f"Génération standard (repli texte) : {e}")
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

    print(f"=== Début de la veille pour {edition_label} ===")

    topics_data = []
    themes = [
        ("ia", "Avancées de l'IA"),
        ("sport", "Data dans le Sport"),
        ("demat", "Dématérialisation")
    ]

    for key, label in themes:
        articles = fetch_recent_articles(FEEDS[key])
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
        except Exception:
            editions = []

    editions = [e for e in editions if e.get("id") != edition_id]
    editions.insert(0, new_edition)

    with open(editions_file, "w", encoding="utf-8") as f:
        json.dump(editions, f, indent=2, ensure_ascii=False)

    print("=== Veille générée et enregistrée avec succès dans editions.json ===")

if __name__ == "__main__":
    main()
