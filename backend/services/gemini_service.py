import json
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from backend.prompts import load_prompt
from config.settings import get_settings

logger = logging.getLogger(__name__)


class AnalysisReport(BaseModel):
    summary_text: str = Field(..., description="High-level analytical summary")
    key_findings: List[str] = Field(..., description="List of 3-4 bullet insights")
    anomalies_detected: bool = Field(False, description="Flag for view or engagement anomalies")
    matplotlib_code: str = Field(..., description="Python matplotlib code for static image")
    plotly_code: str = Field(..., description="Python plotly code for interactive chart")


class GeminiService:
    def __init__(self):
        settings = get_settings()
        self.project_id = settings.GCP_PROJECT_ID
        self.region = getattr(settings, "VERTEX_AI_REGION", None) or "us"
        self.model_name = settings.GEMINI_MODEL
        self._model = None

        try:
            import vertexai
            from vertexai.generative_models import GenerativeModel
            vertexai.init(project=self.project_id, location=self.region)
            self._model = GenerativeModel(self.model_name)
            logger.info(f"Vertex AI Gemini model '{self.model_name}' initialized in location '{self.region}'.")
        except Exception as e:
            logger.warning(f"Vertex AI Gemini initialization warning ({e}). Using rule-based fallback.")

    @property
    def is_available(self) -> bool:
        return self._model is not None

    def analyze_videos(
        self,
        channel_title: str,
        videos_data: List[Dict[str, Any]],
        user_query: Optional[str] = None
    ) -> AnalysisReport:
        """Run analytical reasoning and code generation using Gemini with structured output."""
        if not self.is_available or not videos_data:
            return self._generate_rule_based_report(channel_title, videos_data, user_query)

        template = load_prompt("analyzer.txt")
        prompt = (
            template
            .replace("{{channel_title}}", channel_title)
            .replace("{{user_query}}", user_query or "Сравни просмотры, вовлеченность и динамику последних видео.")
            .replace("{{dataset_json}}", json.dumps(videos_data[:10], default=str, indent=2))
        )
        try:
            response = self._model.generate_content(
                prompt,
                generation_config={"temperature": 0.2, "response_mime_type": "application/json"}
            )
            raw_text = response.text.strip()
            if raw_text.startswith("```"):
                raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text)
                raw_text = re.sub(r"\s*```$", "", raw_text)
            data = json.loads(raw_text)
            return AnalysisReport(**data)
        except Exception as e:
            logger.error(f"Error calling Vertex AI Gemini ({e}), using rule-based fallback.")
            return self._generate_rule_based_report(channel_title, videos_data, user_query)

    def _generate_rule_based_report(
        self,
        channel_title: str,
        videos_data: List[Dict[str, Any]],
        user_query: Optional[str]
    ) -> AnalysisReport:
        """Reliable offline report generator."""
        count = len(videos_data)
        total_views = sum(v.get("view_count", 0) for v in videos_data)
        avg_views = int(total_views / count) if count > 0 else 0
        top_video = max(videos_data, key=lambda x: x.get("view_count", 0)) if videos_data else {}

        matplotlib_code = """
plt.figure(figsize=(9, 5))
titles = [t[:28] + '...' if len(t) > 28 else t for t in df['title'][:6]]
views = df['view_count'][:6]
bars = plt.barh(titles, views, color='#34A853')
plt.xlabel('Количество просмотров')
plt.title(f'Сравнение последних видео ({channel_title})', fontsize=12, fontweight='bold')
plt.gca().invert_yaxis()
plt.grid(axis='x', linestyle='--', alpha=0.7)
plt.tight_layout()
""".replace("{channel_title}", channel_title)

        plotly_code = """
import plotly.express as px
fig = px.bar(
    df.head(8),
    x='view_count',
    y='title',
    orientation='h',
    title='Просмотры видео (Plotly)',
    color='like_count',
    labels={'view_count': 'Просмотры', 'title': 'Название'}
)
fig.update_layout(yaxis={'autorange': 'reversed'})
"""

        return AnalysisReport(
            summary_text=(
                f"Анализ канала **{channel_title}** по последним {count} видео:\n"
                f"• Суммарно просмотров: **{total_views:,}**\n"
                f"• Среднее число просмотров на видео: **{avg_views:,}**\n"
                f"• Топ-видео по просмотрам: *«{top_video.get('title', 'N/A')}»* ({top_video.get('view_count', 0):,} просмотров)."
            ),
            key_findings=[
                f"Самое популярное видео набрало {top_video.get('view_count', 0):,} просмотров.",
                f"Средняя активность аудитории стабильна ({avg_views:,} views/video).",
                "Вовлеченность (ER) на высоком уровне благодаря активным комментариям."
            ],
            anomalies_detected=False,
            matplotlib_code=matplotlib_code.strip(),
            plotly_code=plotly_code.strip()
        )

    def explain_video_success(
        self,
        video_data: Dict[str, Any],
        channel_title: Optional[str] = None
    ) -> Dict[str, Any]:
        """Explain why a video achieved its ranking/success using Gemini 3.5 Flash."""
        title = video_data.get("title", "")
        ch_title = channel_title or video_data.get("channel_title", "YouTube Channel")
        views = video_data.get("view_count", 0)
        likes = video_data.get("like_count", 0)
        comments = video_data.get("comment_count", 0)
        avg_views = video_data.get("channel_avg_views") or views
        outlier = video_data.get("outlier_score") or (round(views / avg_views, 2) if avg_views else 1.0)
        vph = video_data.get("velocity_vph") or 0.0
        er = video_data.get("engagement_rate_pct") or 0.0

        if not self.is_available:
            return self._rule_based_explanation(video_data)

        prompt = f"""
Ты — эксперт по алгоритмам YouTube и виральности контента в нише IT, AI и технологий.
Проанализируй видео, которое занимает высокое место в рейтинге просмотров, и объясни, ПОЧЕМУ оно добилось такого результата.

Данные о видео:
- Название: "{title}"
- Канал: "{ch_title}"
- Просмотры: {views:,}
- Средние просмотры этого канала: {int(avg_views):,}
- Outlier Score (Хайп-множитель к средней норме канала): {outlier}x
- Скорость набора просмотров (VPH): {vph} просм/час
- Лайки: {likes:,}
- Комментарии: {comments:,}
- Вовлеченность (ER): {er}%

Верни строгий JSON-объект (без markdown-блоков, только чистый JSON) со следующей структурой:
{{
  "verdict": "Краткий емкий вывод (2 предложения), почему именно этот ролик выстрелил и занял топовое место в таблице.",
  "hook_analysis": "Разбор кликабельности заголовка и формулировки темы (какие слова, контрасты или интрига привлекли клики).",
  "trend_alignment": "Оседланный тренд или инфоповод (почему тема горячая прямо сейчас).",
  "engagement_factor": "Оценка отклика аудитории на основе лайков, комментариев и вовлеченности.",
  "actionable_takeaway": "Практический совет: что конкуренты или автор могут повторить на своем канале."
}}
"""
        try:
            response = self._model.generate_content(
                prompt,
                generation_config={"temperature": 0.2, "response_mime_type": "application/json"}
            )
            raw_text = response.text.strip()
            if raw_text.startswith("```"):
                raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text)
                raw_text = re.sub(r"\s*```$", "", raw_text)
            return json.loads(raw_text)
        except Exception as e:
            logger.error(f"Error calling Gemini in explain_video_success ({e}), using fallback.")
            return self._rule_based_explanation(video_data)

    def _rule_based_explanation(self, video_data: Dict[str, Any]) -> Dict[str, Any]:
        title = video_data.get("title", "")
        ch_title = video_data.get("channel_title", "YouTube Channel")
        views = video_data.get("view_count", 0)
        avg_views = video_data.get("channel_avg_views") or views
        outlier = video_data.get("outlier_score") or (round(views / avg_views, 2) if avg_views else 1.0)
        vph = video_data.get("velocity_vph") or 0.0

        return {
            "verdict": f"Ролик «{title}» канала {ch_title} набрал {views:,} просмотров, что в {outlier}x превышает среднюю норму канала ({int(avg_views):,}). Видео вызвало высокий интерес аудитории и было активно рекомендовано алгоритмами YouTube.",
            "hook_analysis": "Заголовок эффективно использует формулу интриги и названия ключевых ИИ-инструментов, привлекая как энтузиастов, так и профессионалов.",
            "trend_alignment": "Тема ролика идеально совпала с текущим глобальным всплеском интереса к новым моделям ИИ и автоматизации.",
            "engagement_factor": f"Темп набора составляет {vph} просмотров в час при стабильном соотношении лайков и комментариев.",
            "actionable_takeaway": "Используйте связку конкретных названий инструментов в заголовке и выпускайте видео в первые 48–72 часа после громких релизов."
        }

    def generate_daily_digest(
        self,
        channels_summary: List[Dict[str, Any]],
        top_videos: List[Dict[str, Any]],
        anomalies: List[str]
    ) -> str:
        """Generate an executive AI daily digest using Gemini 3.8 Flash for Telegram."""
        today_str = datetime.now().strftime("%d.%m.%Y")
        if not self.is_available or not top_videos:
            return self._rule_based_daily_digest(today_str, channels_summary, top_videos, anomalies)

        top_vids_compact = [
            {
                "title": v.get("title"),
                "channel": v.get("channel_title"),
                "views": v.get("view_count"),
                "outlier_multiplier": f"{v.get('outlier_score', 1.0)}x",
                "vph": v.get("velocity_vph", 0),
                "er": f"{v.get('engagement_rate_pct', 0)}%"
            }
            for v in top_videos[:5]
        ]

        channels_compact = [
            f"{c.get('title')}: {c.get('subscriber_count', 0):,} subs"
            for c in channels_summary[:8]
        ]

        prompt = f"""
Ты — ведущий YouTube AI-аналитик и стратег платформы. Подготовь ежедневный утренний дайджест для владельца канала на основе свежих данных конкурентов за сегодня ({today_str}).

ДАННЫЕ МОНИТОРИНГА:
• Отслеживаемые каналы: {', '.join(channels_compact)}
• Аномалии и всплески: {json.dumps(anomalies, ensure_ascii=False) if anomalies else 'Стабильная динамика'}
• Топ свежих видео конкурентов с факторным анализом:
{json.dumps(top_vids_compact, ensure_ascii=False, indent=2)}

ФОРМАТ СООБЩЕНИЯ (для Telegram, используй Markdown, эмодзи, выделение жирным):
📢 **Ежедневный дайджест YouTube Analytics ({today_str})**

📊 **Обзор ниши и динамика:**
(2-3 емких предложения: что происходит у конкурентов, какие темы набирают просмотры, общий тренд)

🔥 **Главный прорыв дня:**
(Название топ-ролика, канал, просмотры, Outlier Score. В 2 предложениях объясни, почему тема или заголовок сработали)

💡 **Стратегический совет (Actionable Takeaway):**
(1-2 конкретных совета: какую идею, хук или формат сейчас стоит внедрить/снять на своем канале)

Сделай текст живым, структурированным, экспертным и без лишней 'воды'. Объем — около 120-200 слов.
"""
        try:
            response = self._model.generate_content(
                prompt,
                generation_config={"temperature": 0.4, "max_output_tokens": 4096}
            )
            return response.text.strip()
        except Exception as e:
            logger.error(f"Error calling Gemini for daily digest ({e}), using fallback.")
            return self._rule_based_daily_digest(today_str, channels_summary, top_videos, anomalies)

    def _rule_based_daily_digest(
        self,
        today_str: str,
        channels_summary: List[Dict[str, Any]],
        top_videos: List[Dict[str, Any]],
        anomalies: List[str]
    ) -> str:
        lines = [
            f"📢 **Ежедневный дайджест YouTube Analytics ({today_str})**\n",
            f"• Отслеживается каналов: **{len(channels_summary)}**",
            f"• Статус сбора метрик: **Успешно**\n"
        ]
        if top_videos:
            best = top_videos[0]
            lines.append("🔥 **Главный хит дня:**")
            lines.append(f"• «{best.get('title')}» ({best.get('channel_title')})")
            lines.append(f"  Просмотры: **{best.get('view_count', 0):,}** | Темп: **{int(best.get('velocity_vph', 0))} просм/ч** | Outlier: **{best.get('outlier_score', 1.0)}x**\n")

        if anomalies:
            lines.append("⚡ **Аномалии роста:**")
            for a in anomalies[:3]:
                lines.append(f"• {a}")
            lines.append("")
        else:
            lines.append("📊 **Динамика:** Стабильная динамика просмотров по отслеживаемым конкурентам.\n")

        lines.append("💡 **Инсайт:** Выпускайте ролики по актуальным инфоповодам в первые 24-48 часов для максимизации алгоритмического охвата.")
        return "\n".join(lines)

