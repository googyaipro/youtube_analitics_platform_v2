# 📖 User Guide & Analytics Methodology

Welcome to **YouTube Analytics Platform** — an intelligent system for competitor tracking, viral anomaly detection, and deep AI-powered video breakdown.

---

## 1. 🚀 Architecture & How the System Works

The platform solves the central challenge for creators and analysts: **separating genuine algorithmic momentum from background noise**.

1. **Thematic Channel Sets**:
   - Organize competitor channels into isolated niches (e.g., *'AI Tools'*, *'Crypto'*, *'Fintech'*).
   - Each set is analyzed independently to reveal niche dynamics and top performers.
2. **Direct YouTube Data API v3 Integration**:
   - Queries the official YouTube API to fetch real-time video metrics: views, likes, comments, publication timestamps, and duration.
3. **Secure BYOK (Bring Your Own Key) Security**:
   - Use your own personal YouTube Data API and Google Gemini API keys.
   - Keys are encrypted with symmetric **AES-256 (Fernet)** and decrypted exclusively in-memory when making API calls.
4. **Automated Telegram Delivery**:
   - Receive executive AI digests and alerts right in your Telegram messenger according to your custom schedule and timezone.

---

## 2. ⚙️ How the System Analyzes Data (Methodology)

Raw view counts can be misleading: 50,000 views for a creator with 5 million subscribers is underperformance, while for a channel with 5,000 subscribers, it represents a massive viral breakout. The platform applies **normalized relative analysis**:

1. **Channel Historical Baseline Calculation**:
   - Computes rolling median and baseline performance for each creator across recent uploads.
   - Normalizes comparisons across channels of drastically different audience sizes.
2. **Multi-Vector Anomaly Detection**:
   - Every video is evaluated across baseline multiplier, real-time velocity, and engagement depth.
3. **Format Classification**:
   - Videos are split into **🎬 Long-form Videos** and **📱 Shorts** (<= 60 seconds) to account for differing feed distribution algorithms.

---

## 3. 📊 Key Metrics & Indicators Explained

### 🚀 Outlier Score (Baseline Multiplier)
The definitive indicator of algorithmic breakout, measuring how many times a video outperformed the channel's standard baseline:
* **`1.0x` (Baseline / Standard Upload)**: Performance aligns with normal expectations for core subscribers.
* **`📈 1.5x – 1.9x` (Above Baseline / High Performer)**: The video outperformed standard benchmarks by 50%–90%.
* **`🚀 2.0x+` (Viral Hit / Outlier Breakout)**: An algorithmic anomaly. YouTube's recommendation engine (Browse Features & Suggested Videos) pushed the content well beyond existing subscribers. Analyze these videos to replicate successful hooks and positioning.

---

### ⚡ Velocity (VPH — Views Per Hour)
Measures active real-time momentum:
$$\text{VPH} = \frac{\text{View Count}}{\max(\text{Age in Hours}, 1)}$$
* **Why VPH Matters**: A 3-month-old video with 100,000 views is stagnant (~10 VPH). A video released 3 hours ago with 6,000 views has a velocity of **2,000 VPH** — pinpointing today's breakout trend.
* **Badge `⚡ 100+ views/h`**: Highlights videos with strong ongoing algorithmic momentum.

---

### 💬 Engagement Rate (ER%)
Reflects audience emotional resonance and willingness to interact:
$$\text{ER} = \frac{\text{Likes} + \text{Comments}}{\text{Views}} \times 100\%$$
* **`1.0% – 2.0%`**: Standard engagement for informational content.
* **`💬 ER ≥ 2.5%`**: High resonance. Viewers are actively commenting, debating, and liking — a key ranking signal for YouTube algorithms.

---

### 💎 Views-to-Subscribers Ratio (% Views / Subs)
Measures penetration outside the subscriber base:
$$\text{Views-to-Subs} = \frac{\text{Views}}{\text{Channel Subscriber Count}} \times 100\%$$
* **`< 20%`**: Reaching only a subset of core subscribers.
* **`20% – 80%`**: Healthy penetration of existing subscriber base.
* **`💎 ≥ 100%`**: The video surpassed the channel's entire subscriber count, penetrating broad cold traffic.

---

## 4. 🧠 AI Video Breakdown (Google Gemini)

Click **'🧠 AI Breakdown'** in the dashboard or send `/explain <number>` to the Telegram bot. Gemini analyzes the video across 4 strategic pillars:

1. **🎯 Verdict**:
   - The fundamental driver behind the video's success (psychological trigger, paradigm shift, high utility).
2. **🎣 Hook & Packaging**:
   - Breakdown of thumbnail packaging, title intrigue formula, and first 30-second retention mechanics.
3. **🔥 Trend Alignment**:
   - Macro or micro industry wave capitalized on by the creator.
4. **💡 Creator Takeaway**:
   - Actionable guidelines on how you can adapt this structure and topic for your own content.

---

## 5. 🤖 Telegram Bot Commands

| Command | Action |
| :--- | :--- |
| `/menu` | Open clean interactive menu with buttons |
| `/top` | View top 10 videos with badges and instant explain buttons |
| `/explain <#>` | Run deep AI breakdown on video # from the top list |
| `/digest` | Generate on-demand Executive AI Niche Digest |
| `/sets` | View channel sets and switch active set |
| `/status` | Check API key status and schedule configuration |
| `/lang` | Switch preferred language (`ru`, `en`, `de`, `fi`, `ka`) |
| `/help` | Display quick commands cheat sheet |
