# 📖 Vollständiges Benutzerhandbuch & Analyse-Methodik

Willkommen bei der **YouTube Analytics Platform** — dem intelligenten System zur Konkurrenzbeobachtung, Erkennung viraler Anomalien und tiefgehenden KI-Erfolgsanalyse.

---

## 1. 🔑 Hinzufügen persönlicher API-Schlüssel (BYOK)

Die Plattform nutzt eine sichere **BYOK-Architektur (Bring Your Own Key)**: Sie verwenden Ihre eigenen kostenlosen Kontingente von Google und YouTube. Alle Schlüssel werden mit **AES-256 (Fernet)** verschlüsselt und ausschließlich im Arbeitsspeicher für API-Anfragen entschlüsselt.

### Wo konfigurieren:
Wählen Sie im linken Menü **«🔑 Profil»** (*Profile*).

### Schritt 1. YouTube Data API v3 Schlüssel
* **Zweck:** Abruf aktueller Metriken von YouTube (Aufrufe, Likes, Kommentare, Veröffentlichungsdaten, Abonnentenzahlen).
* **Wo erhältlich (kostenlos):**
  1. Öffnen Sie die [Google Cloud Console](https://console.cloud.google.com/).
  2. Aktivieren Sie die Bibliothek **YouTube Data API v3** (*APIs & Services → Library*).
  3. Erstellen Sie unter *Credentials* einen neuen API-Schlüssel (**«Create Credentials» → «API key»**).
* **Hinzufügen:**
  1. Schlüssel in **«1. YouTube Data API Schlüssel»** einfügen.
  2. Auf **«🧪 Schlüssel prüfen»** klicken. Bei Erfolg wechselt der Status auf **`🟢 Gültig`**.

### Schritt 2. Google Gemini API Schlüssel
* **Zweck:** Interaktiver KI-Analyst, Video-Erfolgsanalysen und tägliche Nischen-Zusammenfassungen.
* **Wo erhältlich (kostenlos):**
  1. Öffnen Sie [Google AI Studio](https://aistudio.google.com/).
  2. Klicken Sie auf **«Get API key» → «Create API key»**.
* **Hinzufügen:**
  1. Schlüssel in **«2. Gemini API Schlüssel»** einfügen.
  2. Auf **«🧪 Schlüssel prüfen»** klicken.
* **Schritt 3:** Unten auf **«💾 API-Schlüssel speichern»** klicken.

---

## 2. 🤖 Telegram-Benachrichtigungen einrichten

Durch die Verknüpfung mit Telegram erhalten Sie geplante Executive-Digests und können Analysen direkt per Bot abrufen.

### Schritt 1. Verknüpfungscode generieren
1. Im Bereich **«🔑 Profil»** in der rechten Spalte auf **«🔗 Telegram verknüpfen»** klicken.
2. Sie erhalten:
   - Einen direkten Link: **`👉 Telegram-Bot öffnen`**.
   - Einen 16-stelligen Einmalcode (z. B. `a1b2c3d4e5f67890`).

### Schritt 2. Im Bot aktivieren
1. Öffnen Sie den Bot in Telegram und senden Sie:
   ```text
   /start <Ihr_16-stelliger_Code>
   ```
2. Der Bot bestätigt: *«🎉 Konto erfolgreich verknüpft!»* und stellt die Sprache automatisch ein.
3. Im Web-Dashboard auf **«🔄 Status prüfen»** klicken.

### Schritt 3. Zeitplan konfigurieren
1. Gehen Sie zu **«⚙️ Kanal-Sets»** (*Channel Sets*).
2. Wählen Sie das Set aus und stellen Sie die Sendezeit, Zeitzone und Wochentage ein.
3. Aktivieren Sie **«✅ Automatischen Versand aktivieren»** und speichern Sie.

---

## 3. 📊 Felder, Metriken und Diagramme erklärt

### «🏠 Startseite» (Home)
* **KPI-Karten:** Kanäle im Set, analysierte Videos, Gesamtaufrufe, Durchschnitt pro Video und virale Hits ($Outlier \ge 2.0x$).
* **Tabelle Top-Videos:**
  - **Aufrufe:** Aktuelle Gesamtzahl.
  - **Velocity (VPH — Aufrufe pro Stunde):** Echtzeit-Schwung. Zeigt, welche Videos der YouTube-Algorithmus aktuell aktiv empfiehlt.
  - **Outlier Score (Faktor zur Kanalnorm):**
    - `1.0x`: Kanal-Durchschnitt.
    - `📈 1.5x – 1.9x`: Überdurchschnittlich (+50–90%).
    - `🚀 2.0x+`: Viraler Durchbruch über die Abonnentenbasis hinaus.
  - **Engagement Rate (ER%):** $\frac{\text{Likes} + \text{Kommentare}}{\text{Aufrufe}} \times 100\%$.
  - **Badges:** `🎬 Video` / `📱 Shorts`, `🚀 Hit 2.5x`, `⚡ 250 Aufrufe/h`, `💎 140% zu Abos`.
  - **«🧠 AI Analyse»:** Tiefgehender KI-Bericht (Urteil, Hook & Verpackung, Trend-Ausrichtung, Handlungsempfehlung).

### «📈 Dynamik» (Dynamics)
* **Balkendiagramme:** Abonnenten- und Aufrufverteilung der Konkurrenten.
* **Virale Streumatrix (Scatter Chart):** Aufrufe vs. Outlier Score / VPH — trennt alte Videos von aktuellen Trend-Raketen.
* **Format-Verteilung:** Anteil Shorts vs. Langformat.

### «⚙️ Kanal-Sets»
* Verwaltung thematischer Nischen und Hinzufügen von Kanälen via `@handle`, URL oder Channel-ID.

### «💬 KI-Analyst»
* Direkte strategische Fragen an Gemini zum aktuellen Kanal-Set.

### «📋 Logs & KI-Diagnose»
* Detaillierte Prompt- und Antwort-Telemetrie mit genauer Modellversion und Antwortzeit.

---

## 4. 🤖 Telegram-Befehle

| Befehl | Aktion |
| :--- | :--- |
| `/menu` | Interaktives Befehlsmenü mit Buttons öffnen |
| `/top` | Top 10 Videos mit Badges und Analyse-Buttons |
| `/explain <nr>` | Tiefgehende KI-Erfolgsanalyse starten |
| `/digest` | Aktuellen Executive-KI-Digest generieren |
| `/sets` | Kanal-Sets anzeigen und auswählen |
| `/status` | Status der API-Schlüssel und Zeitpläne prüfen |
| `/lang` | Sprache anpassen (`ru`, `en`, `de`, `fi`, `ka`) |
| `/help` | Übersicht aller Befehle anzeigen |
