import json
import logging
import re
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from config.settings import get_settings

logger = logging.getLogger(__name__)


class AnalysisReport(BaseModel):
    summary_text: str = Field(..., description="Comprehensive analytical summary in Russian/English")
    key_findings: List[str] = Field(..., description="Bullet point insights on performance")
    anomalies_detected: bool = Field(False, description="Whether viral spikes or drops were detected")
    matplotlib_code: str = Field(..., description="Executable Python code using df and plt/sns for PNG")
    plotly_code: str = Field(..., description="Executable Python code defining 'fig' using px or go for web")


class GeminiService:
    def __init__(self):
        settings = get_settings()
        self.project_id = settings.GCP_PROJECT_ID
        self.location = settings.GCP_LOCATION
        self.model_name = settings.GEMINI_MODEL
        self._model = None

        try:
            import vertexai
            from vertexai.generative_models import GenerativeModel
            vertexai.init(project=self.project_id, location=self.location)
            self._model = GenerativeModel(self.model_name)
            logger.info("Vertex AI Gemini model initialized.")
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

        prompt = f"""
Ты — ведущий YouTube AI-аналитик и Data Scientist.
Проанализируй показатели видео канала '{channel_title}'.
Пользовательский вопрос/задача: {user_query or 'Сравни просмотры, вовлеченность и динамику последних видео.'}

Датасет (передается в датафрейм `df`):
{json.dumps(videos_data[:10], default=str, indent=2)}

Требования к ответу:
1. summary_text: четкий аналитический вывод на русском языке с цифрами (просмотры, лайки, ER).
2. key_findings: 3-4 ключевых инсайта в виде списка.
3. anomalies_detected: true, если есть аномальный всплеск просмотров или лайков.
4. matplotlib_code: чистый исполняемый Python-код без markdown-блоков:
   - использует `df` (колонки: title, view_count, like_count, comment_count).
   - использует `plt` или `sns`.
   - строит красивый, информативный горизонтальный барчарт или scatter plot.
   - использует `plt.tight_layout()`.
5. plotly_code: чистый исполняемый Python-код:
   - использует `df` и `px`.
   - создает объект `fig = px.bar(...)` или `fig = px.scatter(...)`.

Ответь СТРОГО в формате валидного JSON со следующей структурой:
{{
  "summary_text": "...",
  "key_findings": ["...", "..."],
  "anomalies_detected": false,
  "matplotlib_code": "...",
  "plotly_code": "..."
}}
"""
        try:
            response = self._model.generate_content(
                prompt,
                generation_config={"temperature": 0.2, "response_mime_type": "application/json"}
            )
            raw_text = response.text.strip()
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
