# 📖 Complete User Guide & Analytics Methodology

Welcome to **YouTube Analytics Platform** — an intelligent system for competitor tracking, viral anomaly detection, and deep AI-powered video breakdown.

---

## 1. 🔑 Adding Personal API Keys (BYOK)

The platform operates on a secure **BYOK (Bring Your Own Key)** architecture: you utilize your own free quotas from Google and YouTube. All keys are encrypted using symmetric **AES-256 (Fernet)** and decrypted strictly in memory at the moment an API call is made.

### Where to Configure:
Navigate to **'🔑 Profile'** in the left sidebar.

### Step 1. YouTube Data API v3 Key
* **Purpose:** Collects up-to-date YouTube metrics (views, likes, comments, publication timestamps, duration, subscriber counts).
* **Where to Obtain (Free):**
  1. Visit [Google Cloud Console](https://console.cloud.google.com/).
  2. Create a project and enable the **YouTube Data API v3** library (*APIs & Services → Library*).
  3. Under *Credentials*, click **'Create Credentials' → 'API key'**.
* **How to Add:**
  1. Paste your key into **'1. YouTube Data API Key'** (format: `AIzaSy...`).
  2. Click **'🧪 Test Key'**. The platform runs a test request. Upon success, the status turns **`🟢 Valid`**.

### Step 2. Google Gemini API Key
* **Purpose:** Powers the Interactive AI Analyst, deep qualitative video breakdowns, and daily niche digests.
* **Where to Obtain (Free):**
  1. Open [Google AI Studio](https://aistudio.google.com/).
  2. Click **'Get API key' → 'Create API key'**.
* **How to Add:**
  1. Paste your key into **'2. Gemini API Key'** (format: `AIzaSy...`).
  2. Click **'🧪 Test Key'** to verify connectivity with Gemini.
* **Step 3:** Click the blue **'💾 Save API Keys'** button at the bottom. Your keys are securely encrypted and saved.

---

## 2. 🤖 Subscribing to Telegram Scheduled Delivery

Linking Telegram allows you to receive automated morning/evening executive digests and perform on-demand AI breakdowns via bot commands.

### Step 1. Generate Binding Code in Profile
1. On the **'🔑 Profile'** page, locate the right-hand card **'🤖 Telegram Integration'**.
2. Click **'🔗 Link Telegram Account'**.
3. The platform generates:
   - A direct link: **`👉 Open Telegram Bot`**.
   - A unique 16-character one-time binding code (e.g., `a1b2c3d4e5f67890`).

### Step 2. Activate in Telegram
1. Click the link or open your bot in Telegram.
2. Send:
   ```text
   /start <your_16_char_code>
   ```
   *(or simply send the 16-character code as a regular chat message)*.
3. The bot confirms binding: *'🎉 Account successfully linked!'*, adapts command descriptions to your language, and clears redundant keyboards.
4. Back in the web dashboard, click **'🔄 Check Status'** to view the `🟢 Linked` badge and test via **'🔔 Send Test Notification'**.

### Step 3. Configure Digest Schedule
1. Open **'⚙️ Channel Sets'**.
2. Select or create a channel set and configure the **Scheduler**:
   - **Delivery Time:** choose your preferred time (e.g., `09:30` or `18:00`).
   - **Timezone:** set your local timezone (e.g., `America/New_York`, `Europe/London`, `UTC`).
   - **Days of Week:** select delivery days (e.g., Mon–Fri or all 7 days).
   - **Checkbox:** enable **`✅ Enable Scheduled Auto-Digest`**.
3. Click **'Save Channel Set'**. The bot will deliver digests on schedule.

---

## 3. 📊 Dashboard Fields, Metrics & Charts Explained

### '🏠 Home' (Overview & Factor Analysis)

#### 1. Top KPI Summary Cards:
* **Channels in Set:** count of tracked competitor channels in the active set.
* **Videos Analyzed:** total video dataset size collected.
* **Total Views:** gross attention volume accumulated by the set.
* **Average per Video:** arithmetic mean of views (niche benchmark).
* **Viral Hits:** count of breakout videos with Outlier Score $\ge 2.0x$.

#### 2. 'Top Videos & Factor Analysis' Table:
* **Video Title & Channel:** title and creator with direct links to YouTube.
* **Views:** current absolute view count.
* **Velocity (VPH — Views Per Hour):**
  $$\text{VPH} = \frac{\text{Views}}{\max(\text{Age in Hours}, 1)}$$
  *Measures real-time momentum.* A 3-month-old video with 100,000 views has ~10 VPH (stagnant). A 3-hour-old video with 6,000 views has **2,000 VPH** — YouTube's recommendation engine is actively promoting it right now.
* **Outlier Score (Baseline Multiplier):**
  $$\text{Outlier} = \frac{\text{Video Views}}{\text{Channel Historical Median Views}}$$
  *The core anomaly indicator:*
  - `1.0x` — Normal performance for the channel's subscriber base.
  - `📈 1.5x – 1.9x` — Above baseline (+50–90%). Strong topic interest.
  - `🚀 2.0x+` — Viral breakout. Promoted to broad external audiences via Browse and Suggested features.
* **Engagement Rate (ER%):**
  $$\text{ER} = \frac{\text{Likes} + \text{Comments}}{\text{Views}} \times 100\%$$
  - Baseline: `1.0% – 2.0%`.
  - `💬 ER ≥ 2.5%`: high emotional resonance, strong audience debate.
* **Badges:**
  - `🎬 Video` / `📱 Shorts` — content format.
  - `🚀 Hit 2.5x` — outlier multiplier over channel baseline.
  - `⚡ 250 views/h` — high ongoing velocity.
  - `💎 140% of subs` — views exceeded total subscribers (broke out of core bubble).
* **'🧠 AI Breakdown' Button:** initiates Gemini deep breakdown (Verdict, Hook & Packaging, Trend Alignment, Creator Takeaway).

---

### '📈 Dynamics' (Niche Visualization)

* **🏆 Top Channels by Subscribers (Bar Chart):** audience size distribution across competitors.
* **👁️ Channel Aggregate Views (Bar Chart):** reveals creators generating actual attention volume vs. stagnant sub counts.
* **🎯 Virality Scatter Matrix (Views vs. Outlier Score / VPH):**
  - Each bubble represents a single video.
  - *Lower zone:* routine standard uploads.
  - *Lower right:* high historical views with near-zero current velocity.
  - *Upper zone:* high-velocity viral outliers worth dissecting.
* **📊 Format Breakdown (Pie Chart):** ratio of Shorts vs. long-form video distribution.

---

### '⚙️ Channel Sets'

* **Set Name & Description:** thematic category (e.g., *'AI Automation'*, *'Fintech Podcasts'*).
* **'📺 Channels in Set' Tab:**
  - Add Channel: supports `@handle` (e.g., `@mkbhd`), direct channel URL, or Channel ID (`UC...`).
  - Channel cards: avatar, subscriber count, total views, and sync timestamp.
  - **'Sync Now' Button:** triggers on-demand data refresh via YouTube API.

---

### '💬 AI Analyst' (Interactive Consultation)
* Freeform prompt field to query Gemini with the active channel set context:
  - *'Which angles drove the highest velocity this week?'*
  - *'Compare title hooks across the top 3 channels.'*
  - *'Generate 5 video concepts adapting the week's top viral formulas.'*

---

### '📋 Logs & AI Diagnostics' (System Logs)
* **AI & LLM Telemetry:** prompt text, exact model version, latency in seconds, raw JSON, and parsed breakdown.
* **System Events:** Telegram webhook payloads, autonomous scheduler triggers, and background workers.
* **Live Model Tester:** execute real-time test prompts to verify key validity and response latency.

---

## 4. 🤖 Telegram Bot Quick Commands

| Command | Action |
| :--- | :--- |
| `/menu` | Open interactive menu with buttons |
| `/top` | Top 10 videos with badges and breakdown buttons |
| `/explain <#>` | Run deep AI breakdown on video # from the top list |
| `/digest` | Generate on-demand Executive AI Niche Digest |
| `/sets` | View channel sets and switch active set |
| `/status` | Check API key status and schedule configuration |
| `/lang` | Switch preferred language (`ru`, `en`, `de`, `fi`, `ka`) |
| `/help` | Display quick commands cheat sheet |
