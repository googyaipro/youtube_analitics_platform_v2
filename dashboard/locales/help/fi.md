# 📖 Käyttöopas ja analyysimenetelmät

Tervetuloa **YouTube Analytics Platform** -alustalle — älykkääseen järjestelmään kilpailijaseurantaan, viraalianomalioiden havaitsemiseen ja syvälliseen tekoälyanalyysiin.

---

## 1. 🚀 Järjestelmän arkkitehtuuri ja toimintaperiaate

Alusta ratkaisee sisällöntuottajien ja analyytikoiden keskeisen haasteen: **todellisten algoritmisten trendien erottamisen taustakohinasta**.

1. **Kanavasetit (Channel Sets)**:
   - Ryhmittele kilpailijoiden kanavat aihepiireittäin (esim. *«Tekoälytyökalut»*, *«Krypto»*, *«Talous»*).
   - Jokainen setti analysoidaan erillisenä kokonaisuutena parhaiden videoiden ja trendien löytämiseksi.
2. **Suora YouTube Data API v3 -integraatio**:
   - Hakee reaaliaikaiset metriikat: katselukerrat, tykkäykset, kommentit, julkaisuajat ja videoiden kestot.
3. **Turvallinen BYOK (Bring Your Own Key) -arkkitehtuuri**:
   - Käytä omia YouTube- ja Google Gemini -avaimiasi.
   - Avaimet salataan symmetrisellä **AES-256 (Fernet)** -salauksella ja puretaan vain muistissa pyynnön ajaksi.
4. **Automaattiset Telegram-koosteet**:
   - Saat ajastetut johdon yhteenvedot ja hälytykset suoraan Telegramiin haluamassasi aikavyöhykkeessä.

---

## 2. ⚙️ Analyysimenetelmä

Pelkät katselukerrat voivat johtaa harhaan: 50 000 katselukertaa miljoonakanavalle on heikko tulos, kun taas 5 000 tilaajan kanavalle se on massiivinen viraalimenestys. Siksi alusta käyttää **suhteellisia normitettuja mittareita**:

1. **Kanavan perustason laskenta (Baseline)**:
   - Laskee jokaiselle kanavalle katselukertojen liukuvan mediaanin aiemmista julkaisuista.
   - Mahdollistaa eri kokoisten kanavien tasapuolisen vertailun.
2. **Monimuuttuja-anomalia-analyysi**:
   - Jokainen video arvioidaan suhteessa kanavan perustasoon, katselunopeuteen ja sitoutumisasteeseen.
3. **Sisältömuodon jaottelu**:
   - Erottaa toisistaan **🎬 Pitkät videot** ja **📱 Shorts-videot** (enintään 60 s), joiden suosittelualgoritmit toimivat täysin eri tavalla.

---

## 3. 📊 Keskeiset mittarit ja niiden merkitys

### 🚀 Outlier Score (Perustasokerroin / Anomaliapisteet)
Tärkein mittari videon algoritmiselle läpimurrolle:
* **`1.0x` (Perustaso / Normaali video)**: Vastaa kanavan vakiokatsojakunnan normaalia kiinnostusta.
* **`📈 1.5x – 1.9x` (Yli tason / High Performer)**: 50–90 % enemmän katselukertoja kuin kanavalla yleensä.
* **`🚀 2.0x+` (Viraalihitti / Poikkeama)**: Algoritminen läpimurto. YouTube on alkanut suositella videota tilaajakunnan ulkopuolelle. Nämä videot kannattaa tutkia tarkkaan ideoiden ja koukkujen löytämiseksi.

---

### ⚡ Velocity (VPH — Katselukertaa tunnissa)
Mittaa videon reaaliaikaista algoritmista vauhtia:
$$\text{VPH} = \frac{\text{Katselukerrat}}{\max(\text{Videon ikä tunteina}, 1)}$$
* **Miksi VPH on tärkeä**: 3 kuukautta vanha video 100 000 katselukerralla on jo hiipunut (~10 VPH). 3 tuntia sitten julkaistu video 6 000 katselukerralla etenee vauhdilla **2 000 VPH** — osoittaen tämän hetken polttavimman trendin.
* **Merkintä `⚡ 100+ views/h`**: Kertoo voimakkaasta jatkuvasta liikennevirrasta.

---

### 💬 Engagement Rate (ER% — Sitoutumisaste)
Kuvaa yleisön reaktiota ja halua osallistua keskusteluun:
$$\text{ER} = \frac{\text{Tykkäykset} + \text{Kommentit}}{\text{Katselukerrat}} \times 100\%$$
* **`1.0% – 2.0%`**: Tyypillinen taso asiasisällölle.
* **`💬 ER ≥ 2.5%`**: Korkea reaktio. Yleisö keskustelee aktiivisesti — vahva signaali YouTuben suosittelualgoritmille.

---

### 💎 Views-to-Subscribers Ratio (Katselukerrat suhteessa tilaajiin %)
Osoittaa videon kyvyn murtautua kanavan oman tilaajakuplan ulkopuolelle:
$$\text{Views-to-Subs} = \frac{\text{Katselukerrat}}{\text{Kanavan tilaajamäärä}} \times 100\%$$
* **`💎 ≥ 100%`**: Videolla on enemmän katselukertoja kuin kanavalla on tilaajia. Video leviää tehokkaasti kylmälle yleisölle.

---

## 4. 🧠 Tekoälypohjainen analyysi (Google Gemini)

Napsauta **«🧠 AI Analyysi»** -painiketta tai lähetä Telegramissa `/explain <numero>`:
1. **🎯 Tuomio (Verdict)**: Menestyksen keskeinen psykologinen tai sisällöllinen syy.
2. **🎣 Koukku ja paketoiti**: Pikkukuvan, otsikon ja ensimmäisten 30 sekunnin tehokkuusanalyysi.
3. **🔥 Trendin hyödyntäminen**: Mitä toimialan makro- tai mikrotrendiä video hyödyntää.
4. **💡 Suositus sisällöntuottajalle**: Konkreettiset vinkit idean soveltamiseen omissa videoissa.

---

## 5. 🤖 Telegram-botin komennot

| Komento | Toiminto |
| :--- | :--- |
| `/menu` | Avaa interaktiivinen komentovalikko |
| `/top` | Näytä top 10 videot ja pika-analyysipainikkeet |
| `/explain <nro>` | Suorita syvällinen Gemini-analyysi videosta |
| `/digest` | Luo tuore johdon tekoäly-yhteenveto |
| `/sets` | Tarkastele ja vaihda kanavasettiä |
| `/status` | Tarkista API-avainten ja aikataulujen tila |
| `/lang` | Vaihda kieltä (`ru`, `en`, `de`, `fi`, `ka`) |
| `/help` | Komentoluettelo ja pikaohje |
