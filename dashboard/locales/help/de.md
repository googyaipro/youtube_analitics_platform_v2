# 📖 Benutzerhandbuch & Analyse-Methodik

Willkommen bei der **YouTube Analytics Platform** — dem intelligenten System zur Konkurrenzbeobachtung, Erkennung viraler Anomalien und tiefgehenden KI-Erfolgsanalyse.

---

## 1. 🚀 Systemarchitektur & Funktionsweise

Die Plattform löst die zentrale Herausforderung für Creator und Analysten: **Echte algorithmische Trends vom Hintergrundrauschen zu trennen**.

1. **Thematische Kanal-Sets (Channel Sets)**:
   - Gruppieren Sie Kanäle nach Nischen (z. B. *«KI-Tools»*, *«Krypto»*, *«Finanzen»*).
   - Jedes Set wird isoliert analysiert, um spezifische Trends und Top-Performer zu identifizieren.
2. **Direkte Anbindung an die YouTube Data API v3**:
   - Ruft offizielle YouTube-Metriken ab: Aufrufe, Likes, Kommentare, Veröffentlichungsdaten und Videodauer.
3. **Sichere BYOK-Architektur (Bring Your Own Key)**:
   - Verwenden Sie Ihre eigenen API-Schlüssel für YouTube und Google Gemini.
   - Alle Schlüssel werden mit **AES-256 (Fernet)** verschlüsselt und ausschließlich im Arbeitsspeicher für API-Anfragen entschlüsselt.
4. **Automatische Telegram-Zustellung**:
   - Erhalten Sie geplante Executive-Digests und Analysen direkt in Telegram basierend auf Ihrer Zeitzone.

---

## 2. ⚙️ Analysemethodik

Absolute Aufrufzahlen sind trügerisch: 50.000 Aufrufe für einen Kanal mit 5 Millionen Abonnenten sind schwach, während es für einen Kanal mit 5.000 Abonnenten ein gigantischer viraler Durchbruch ist. Die Plattform nutzt **relative normierte Metriken**:

1. **Historische Baseline-Berechnung**:
   - Ermittelt den gleitenden Median der Aufrufe für jeden Kanal aus vergangenen Uploads.
   - Ermöglicht faire Vergleiche zwischen kleinen und großen Kanälen.
2. **Mehrdimensionale Anomalie-Erkennung**:
   - Jedes Video wird anhand des Multiplikators zur Kanalnorm, der aktuellen Geschwindigkeit und der Interaktionsrate bewertet.
3. **Format-Differenzierung**:
   - Unterscheidung zwischen **🎬 Langformat-Videos** und **📱 Shorts** (bis 60 Sekunden), da sich deren Algorithmen grundlegend unterscheiden.

---

## 3. 📊 Metriken & Indikatoren im Detail

### 🚀 Outlier Score (Faktor zur Kanalnorm)
Der wichtigste Indikator für einen viralen Durchbruch:
* **`1.0x` (Norm / Standard-Upload)**: Typische Resonanz der Stammzuschauer.
* **`📈 1.5x – 1.9x` (Überdurchschnittlich / High Performer)**: 50% bis 90% mehr Aufrufe als üblich. Starkes Thema oder überzeugende Verpackung.
* **`🚀 2.0x+` (Virale Anomalie / Hit-Ausreißer)**: Ein algorithmischer Durchbruch. Der YouTube-Empfehlungsalgorithmus spielt das Video weit über die Abonnentenbasis hinaus aus. Diese Videos bieten die besten Vorlagen für eigene Inhalte.

---

### ⚡ Velocity (VPH — Aufrufe pro Stunde)
Zeigt den aktuellen Echtzeit-Schwung:
$$\text{VPH} = \frac{\text{Aufrufe}}{\max(\text{Videoalter in Stunden}, 1)}$$
* **Warum VPH wichtig ist**: Ein 3 Monate altes Video mit 100.000 Aufrufen stagniert meist (~10 VPH). Ein 3 Stunden altes Video mit 6.000 Aufrufen erzielt **2.000 VPH** — und markiert den aktuellen Brennpunkt.
* **Badge `⚡ 100+ views/h`**: Signalisiert anhaltendes algorithmisches Momentum.

---

### 💬 Engagement Rate (ER% — Interaktionsrate)
Misst die emotionale Resonanz und Diskussionsbereitschaft der Zuschauer:
$$\text{ER} = \frac{\text{Likes} + \text{Kommentare}}{\text{Aufrufe}} \times 100\%$$
* **`1.0% – 2.0%`**: Normalbereich für informative Inhalte.
* **`💬 ER ≥ 2.5%`**: Sehr hohe Resonanz. Intensiver Austausch in den Kommentaren — ein starkes Signal für den YouTube-Algorithmus.

---

### 💎 Views-to-Subscribers Ratio (Aufrufe zu Abonnenten %)
Zeigt, wie weit das Video die eigene Abonnentenblase durchbricht:
$$\text{Views-to-Subs} = \frac{\text{Aufrufe}}{\text{Abonnentenzahl des Kanals}} \times 100\%$$
* **`💎 ≥ 100%`**: Das Video hat mehr Aufrufe als der Kanal Abonnenten hat. Es wird massiv an neue, kalte Zielgruppen ausgespielt.

---

## 4. 🧠 KI-Videoanalyse (Google Gemini)

Klicken Sie auf **«🧠 AI Analyse»** oder senden Sie `/explain <nummer>` im Telegram-Bot:
1. **🎯 Urteil (Verdict)**: Der wesentliche psychologische oder inhaltliche Grund für den Erfolg.
2. **🎣 Hook & Verpackung**: Analyse von Thumbnail-Aufbau, Titel-Neugierde und den ersten 30 Sekunden.
3. **🔥 Trend-Ausrichtung**: Welcher Makro- oder Mikrotrend in der Branche genutzt wurde.
4. **💡 Handlungsempfehlung**: Wie Sie die Struktur und Thematik für eigene Videos adaptieren können.

---

## 5. 🤖 Telegram-Befehle

| Befehl | Funktion |
| :--- | :--- |
| `/menu` | Interaktives Befehlsmenü mit Buttons öffnen |
| `/top` | Top-10-Videos mit Badges und Direktanalyse-Buttons |
| `/explain <nr>` | Tiefgehende Gemini-Erfolgsanalyse für Video Nr. starten |
| `/digest` | Aktuellen Executive-KI-Digest der Nische generieren |
| `/sets` | Kanal-Sets anzeigen und aktives Set wechseln |
| `/status` | Status der API-Schlüssel und Zeitpläne prüfen |
| `/lang` | Sprache anpassen (`ru`, `en`, `de`, `fi`, `ka`) |
| `/help` | Übersicht aller Befehle anzeigen |
