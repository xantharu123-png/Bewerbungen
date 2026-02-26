# 💼 JobTracker Pro – Stellenbewerbungs-Manager

Eine Streamlit-App zur automatischen Stellensuche und Bewerbungsverwaltung in der Schweiz.

## 🚀 Features

- **Automatische Stellensuche** auf jobs.ch nach konfigurierbaren Keywords
- **Bewerbungs-Tracker** mit Status (Neu → Beworben → Interview → Zusage/Absage)
- **Unterlagen-Verwaltung** – CV und Anschreiben hochladen (PDF/DOCX)
- **KI-Anschreiben Generator** – massgeschneiderte Anschreiben via Anthropic Claude API
- **Match-Score** – wie gut passt dein CV zur Stelle? (0–100%)
- **Statistiken** – Übersicht, Charts, CSV-Export
- **Lokale Datenbank** – alles wird in `data/jobs.json` gespeichert

## 📦 Installation

```bash
# 1. Repository klonen / herunterladen
cd jobtracker

# 2. Python-Umgebung erstellen (empfohlen)
python -m venv venv
source venv/bin/activate  # Mac/Linux
# oder: venv\Scripts\activate  # Windows

# 3. Abhängigkeiten installieren
pip install -r requirements.txt

# 4. App starten
streamlit run app.py
```

## ⚙️ Konfiguration

1. **Anthropic API Key**: In der Sidebar eingeben (für KI-Features)
   - Hol dir einen Key auf: https://console.anthropic.com
   
2. **Standard-Keywords**: In der Sidebar anpassen (z.B. "ERP Projektleiter", "Business Analyst")

3. **Unterlagen**: Im Tab "Unterlagen" CV und Muster-Anschreiben hochladen

## 🌐 Deployment auf Streamlit Cloud (kostenlos)

```bash
# GitHub Repository erstellen und Code pushen
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_USERNAME/jobtracker.git
git push -u origin main
```

Dann auf https://streamlit.io/cloud → "New app" → Repository auswählen → Deploy

**Wichtig**: API Key als Secret in Streamlit Cloud einrichten:
- Settings → Secrets → `ANTHROPIC_API_KEY = "sk-ant-..."`

## 📁 Dateistruktur

```
jobtracker/
├── app.py              # Haupt-App
├── database.py         # Datenbankfunktionen (JSON-basiert)
├── scraper.py          # Web-Scraping für jobs.ch
├── ai_assistant.py     # Anthropic Claude Integration
├── requirements.txt    # Python-Abhängigkeiten
├── README.md           # Diese Datei
└── data/               # Automatisch erstellt
    ├── jobs.json       # Alle gespeicherten Stellen
    └── documents/      # Hochgeladene Unterlagen
```

## 🔧 Erweiterungsideen

- LinkedIn-Suche integrieren
- Email-Benachrichtigungen bei neuen Stellen
- Automatische tägliche Suche via GitHub Actions
- Kalender-Integration für Interview-Termine
- WhatsApp/Telegram-Notifikationen

## 📝 Hinweise

- Das Scraping von jobs.ch funktioniert über HTTP-Requests + BeautifulSoup
- Bei häufigen Suchen kann jobs.ch temporär blockieren – dann kurz warten
- Alle Daten werden lokal gespeichert, nichts wird in die Cloud geschickt (ausser API-Calls zu Anthropic)
