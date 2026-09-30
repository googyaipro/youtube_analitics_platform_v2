# 📖 Täydellinen käyttöopas ja analyysimenetelmät

Tervetuloa **YouTube Analytics Platform** -alustalle — älykkääseen järjestelmään kilpailijaseurantaan, viraalianomalioiden havaitsemiseen ja syvälliseen tekoälyanalyysiin.

---

## 1. 🔑 Henkilökohtaisten API-avainten lisääminen (BYOK)

Alusta toimii turvallisella **BYOK (Bring Your Own Key)** -mallilla: käytät omia maksuttomia Googlen ja YouTuben kiintiöitäsi. Kaikki avaimet salataan symmetrisellä **AES-256 (Fernet)** -salauksella ja puretaan vain välimuistissa API-pyynnön ajaksi.

### Missä määritetään:
Siirry vasemmasta valikosta kohtaan **«🔑 Profiili»** (*Profile*).

### Vaihe 1. YouTube Data API v3 -avain
* **Tarkoitus:** Hakee tuoreimmat YouTube-tiedot (katselukerrat, tykkäykset, kommentit, julkaisuajat, tilaajamäärät).
* **Mistä saa (ilmainen):**
  1. Siirry [Google Cloud Consoleen](https://console.cloud.google.com/).
  2. Ota käyttöön **YouTube Data API v3** (*APIs & Services → Library*).
  3. Luo uusi API-avain kohdassa *Credentials* (**«Create Credentials» → «API key»**).
* **Lisääminen:**
  1. Liitä avain kenttään **«1. YouTube Data API -avain»**.
  2. Napsauta **«🧪 Testaa avain»**. Onnistumisen jälkeen tila muuttuu muotoon **`🟢 Kelvollinen`**.

### Vaihe 2. Google Gemini API -avain
* **Tarkoitus:** Interaktiivinen tekoäly-analyytikko, videoiden viraalianalyysit ja päivittäiset koosteet.
* **Mistä saa (ilmainen):**
  1. Avaa [Google AI Studio](https://aistudio.google.com/).
  2. Napsauta **«Get API key» → «Create API key»**.
* **Lisääminen:**
  1. Liitä avain kenttään **«2. Gemini API -avain»**.
  2. Napsauta **«🧪 Testaa avain»**.
* **Vaihe 3:** Napsauta alhaalta sinistä painiketta **«💾 Tallenna API-avaimet»**.

---

## 2. 🤖 Telegram-jakelun tilaaminen

Telegramin yhdistäminen mahdollistaa ajastettujen koosteiden vastaanottamisen ja videoiden pika-analyysin suoraan botin kautta.

### Vaihe 1. Yhdistämiskoodin luominen
1. Napsauta profiilisivun oikeassa sarakkeessa painiketta **«🔗 Yhdistä Telegram»**.
2. Järjestelmä luo:
   - Suoran linkin: **`👉 Avaa Telegram-botti`**.
   - 16-merkkisen kertakäyttökoodin (esim. `a1b2c3d4e5f67890`).

### Vaihe 2. Aktivointi Telegramissa
1. Avaa botti Telegramissa ja lähetä:
   ```text
   /start <16-merkkinen_koodi>
   ```
2. Botti vahvistaa: *«🎉 Tili yhdistetty onnistuneesti!»* ja asettaa käyttöliittymän kielen.
3. Napsauta verkkopaneelissa **«🔄 Tarkista tila»**.

### Vaihe 3. Aikataulun määrittäminen
1. Siirry sivulle **«⚙️ Kanavasetit»** (*Channel Sets*).
2. Valitse setti ja aseta lähetysaika, aikavyöhyke ja viikonpäivät.
3. Ota käyttöön **«✅ Ota automaattinen lähetys käyttöön»** ja tallenna.

---

## 3. 📊 Kenttien, mittareiden ja kaavioiden selitykset

### «🏠 Etusivu» (Home)
* **KPI-kortit:** Kanavat setissä, analysoidut videot, kokonaiskatselut, keskiarvo per video ja viraalihitit ($Outlier \ge 2.0x$).
* **Top-videoiden taulukko:**
  - **Katselukerrat:** Nykyinen kokonaismäärä.
  - **Velocity (VPH — Katselua tunnissa):** Reaaliaikainen vauhti, jota YouTube aktiivisesti suosittelee juuri nyt.
  - **Outlier Score (Perustasokerroin):**
    - `1.0x`: Kanavan normaali taso.
    - `📈 1.5x – 1.9x`: Yli tason (+50–90%).
    - `🚀 2.0x+`: Viraaliläpimurto tilaajakunnan ulkopuolelle.
  - **Engagement Rate (ER%):** $\frac{\text{Tykkäykset} + \text{Kommentit}}{\text{Katselukerrat}} \times 100\%$.
  - **Merkinnät:** `🎬 Video` / `📱 Shorts`, `🚀 Hitti 2.5x`, `⚡ 250 kats/h`, `💎 140% tilaajiin`.
  - **«🧠 AI Analyysi»:** Syvällinen raportti (Tuomio, Koukku ja paketoiti, Trendin hyödyntäminen, Suositus).

### «📈 Dynamiikka» (Dynamics)
* **Pylväskaaviot:** Tilaajien ja katselukertojen jakautuminen kilpailijoiden kesken.
* **Viraalihajontakaavio (Scatter Chart):** Katselukerrat vs. Outlier Score / VPH.
* **Muotojakauma:** Shorts- ja pitkien videoiden suhde.

### «⚙️ Kanavasetit»
* Kanavaryhmien hallinta ja kanavien lisääminen tunnisteella (`@handle`), URL-osoitteella tai kanavatunnuksella.

### «💬 Tekoäly-analyytikko»
* Suora strateginen kyselytyökalu Geminille aktiivisesta kanavasetistä.

### «📋 Lokit ja tekoälydiagnostiikka»
* Kyselyjen ja vastausten täydellinen telemetria malliversioineen ja viiveineen.

---

## 4. 🤖 Telegram-botin komennot

| Komento | Toiminto |
| :--- | :--- |
| `/menu` | Avaa interaktiivinen komentovalikko |
| `/top` | Näytä top 10 videot ja analyysipainikkeet |
| `/explain <nro>` | Suorita syvällinen tekoälyanalyysi videosta |
| `/digest` | Luo tuore johdon tekoäly-yhteenveto |
| `/sets` | Tarkastele ja vaihda kanavasettiä |
| `/status` | Tarkista API-avainten ja aikataulujen tila |
| `/lang` | Vaihda kieltä (`ru`, `en`, `de`, `fi`, `ka`) |
| `/help` | Pikaohje komennoista |
