import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple
import httpx

logger = logging.getLogger(__name__)

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
FALLBACK_MODEL_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"

LANGUAGE_PROMPT_NAMES = {
    "ru": "русском (Russian)",
    "en": "английском (English)",
    "de": "немецком (German)",
    "fi": "финском (Finnish)",
    "ka": "грузинском (Georgian - ქართული)"
}


class GeminiService:
    @staticmethod
    def verify_api_key(api_key: Optional[str]) -> Tuple[bool, str]:
        """Test Gemini API key validity from Google AI Studio using a micro-prompt."""
        if not api_key or len(api_key.strip()) < 10:
            return False, "Gemini API key is empty or too short."

        clean_key = api_key.strip()
        body = {
            "contents": [{"role": "user", "parts": [{"text": "Reply with 'OK'."}]}],
            "generationConfig": {"maxOutputTokens": 10}
        }

        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.post(f"{GEMINI_API_URL}?key={clean_key}", json=body)
                if res.status_code == 200:
                    return True, "Gemini API key is valid and connected successfully."
                elif res.status_code == 404:
                    # Try fallback model
                    res2 = client.post(f"{FALLBACK_MODEL_URL}?key={clean_key}", json=body)
                    if res2.status_code == 200:
                        return True, "Gemini API key is valid (using Gemini 1.5 Flash)."
                
                error_msg = res.json().get("error", {}).get("message", f"HTTP {res.status_code}")
                return False, f"Gemini Error: {error_msg}"
        except Exception as e:
            logger.error(f"Error testing Gemini key: {e}")
            return False, f"Network error connecting to Gemini API: {e}"

    @staticmethod
    def _call_gemini(prompt: str, api_key: str, max_tokens: int = 2048, temperature: float = 0.4) -> Optional[str]:
        """Direct HTTP call to Gemini API using user's personal key."""
        if not api_key:
            return None

        body = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens
            }
        }

        try:
            with httpx.Client(timeout=30.0) as client:
                res = client.post(f"{GEMINI_API_URL}?key={api_key.strip()}", json=body)
                if res.status_code != 200:
                    # Try fallback model
                    res = client.post(f"{FALLBACK_MODEL_URL}?key={api_key.strip()}", json=body)
                
                if res.status_code == 200:
                    data = res.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if parts:
                            return parts[0].get("text", "").strip()
                else:
                    logger.error(f"Gemini API returned error {res.status_code}: {res.text}")
        except Exception as e:
            logger.error(f"Exception calling Gemini: {e}")

        return None

    @classmethod
    def explain_video_success(
        cls,
        video_data: Dict[str, Any],
        target_language: str = "ru",
        gemini_api_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """Explain why a specific video outperformed channel averages."""
        title = video_data.get("title", "")
        ch_title = video_data.get("channel_title", "Channel")
        views = video_data.get("view_count", 0)
        avg_views = video_data.get("channel_avg_views") or views
        outlier = video_data.get("outlier_score", 1.0)
        vph = video_data.get("velocity_vph", 0.0)
        er = video_data.get("engagement_rate_pct", 0.0)

        lang_name = LANGUAGE_PROMPT_NAMES.get(target_language, "русском (Russian)")

        if not gemini_api_key:
            return cls._rule_based_explanation(video_data, target_language)

        prompt = f"""
Ты — профессиональный YouTube AI-аналитик и виральный стратег.
Проанализируй видео, которое показало высокий результат просмотров среди конкурентов.

ДАННЫЕ:
- Название: "{title}"
- Канал: "{ch_title}"
- Просмотры: {views:,}
- Средняя норма просмотров автора: {int(avg_views):,}
- Outlier Score (Хайп-множитель к средней норме): {outlier}x
- Скорость набора просмотров (VPH): {vph} просм/час
- Вовлеченность (ER): {er}%

ТРЕБОВАНИЯ:
1. Напиши весь анализ СТРОГО на языке: {lang_name}.
2. Верни чистый JSON-объект без оберток со следующими ключами:
{{
  "verdict": "Краткий емкий вывод (2 предложения), почему именно этот ролик выстрелил и занял высокое место.",
  "hook_analysis": "Разбор кликабельности заголовка и формулировки темы (интрига, триггеры, контраст).",
  "trend_alignment": "Оседланный тренд или инфоповод (почему тема горячая).",
  "engagement_factor": "Оценка отклика аудитории на основе просмотров, скорости и ER.",
  "actionable_takeaway": "Практический совет: что автор может повторить на своем канале."
}}
"""
        response_text = cls._call_gemini(prompt, gemini_api_key, max_tokens=1500, temperature=0.2)
        if response_text:
            try:
                clean_json = re.sub(r"^```(?:json)?\s*", "", response_text.strip())
                clean_json = re.sub(r"\s*```$", "", clean_json)
                return json.loads(clean_json)
            except Exception as e:
                logger.warning(f"Error parsing Gemini JSON: {e}")

        return cls._rule_based_explanation(video_data, target_language)

    @classmethod
    def generate_daily_digest(
        cls,
        set_name: str,
        channels_summary: List[Dict[str, Any]],
        top_videos: List[Dict[str, Any]],
        anomalies: List[str],
        target_language: str = "ru",
        gemini_api_key: Optional[str] = None
    ) -> str:
        """Generate executive AI daily digest tailored to user's channel set and language."""
        lang_name = LANGUAGE_PROMPT_NAMES.get(target_language, "русском (Russian)")

        if not gemini_api_key or not top_videos:
            return cls._rule_based_daily_digest(set_name, channels_summary, top_videos, anomalies, target_language)

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

        prompt = f"""
Ты — ведущий YouTube AI-аналитик и стратег платформы.
Подготовь ежедневный дайджест для владельца тематического набора каналов «{set_name}».

ДАННЫЕ МОНИТОРИНГА:
• Набор каналов: {set_name}
• Отслеживается каналов: {len(channels_summary)}
• Аномалии и всплески: {json.dumps(anomalies, ensure_ascii=False) if anomalies else 'Стабильная динамика'}
• Топ свежих роликов конкурентов с факторным анализом:
{json.dumps(top_vids_compact, ensure_ascii=False, indent=2)}

ТРЕБОВАНИЯ:
1. Напиши весь текст СТРОГО на языке: {lang_name}.
2. Структура сообщения для Telegram (с эмодзи, выделением жирным):
📢 Дайджест YouTube Analytics: {set_name}

📊 Обзор ниши и динамика:
(2-3 емких предложения о том, какие темы и подходы сейчас растут у конкурентов)

🔥 Главный прорыв дня:
(Название топ-ролика, канал, просмотры, Outlier Score. В 2 предложениях объясни, почему тема или заголовок сработали)

💡 Стратегический совет (Actionable Takeaway):
(1-2 конкретных совета: какую тему, хук или формат сейчас стоит внедрить автору)

Объем — около 120-200 слов. Без лишней воды.
"""
        response_text = cls._call_gemini(prompt, gemini_api_key, max_tokens=2500, temperature=0.4)
        if response_text:
            return response_text

        return cls._rule_based_daily_digest(set_name, channels_summary, top_videos, anomalies, target_language)

    @classmethod
    def ask_analyst(
        cls,
        query: str,
        videos_context: List[Dict[str, Any]],
        target_language: str = "ru",
        gemini_api_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """Interactive Q&A with Gemini regarding channel videos."""
        lang_name = LANGUAGE_PROMPT_NAMES.get(target_language, "русском (Russian)")

        if not gemini_api_key:
            return {
                "answer": "Для получения персонального AI-анализа укажите ваш Gemini API ключ в настройках профиля.",
                "key_findings": ["Ключ Gemini не настроен"]
            }

        prompt = f"""
Ты — персональный YouTube AI-аналитик. Ответь на вопрос пользователя на основе предоставленных данных о видео конкурентов.

ВОПРОС ПОЛЬЗОВАТЕЛЯ: "{query}"

ДАННЫЕ О ВИДЕО (ТОП 10):
{json.dumps(videos_context[:10], default=str, ensure_ascii=False, indent=2)}

ТРЕБОВАНИЯ:
1. Ответь СТРОГО на языке: {lang_name}.
2. Дай четкий практический ответ со ссылкой на конкретные названия видео и цифры.
3. Верни чистый JSON следующего вида:
{{
  "answer": "Развернутый ответ эксперта (2-3 абзаца)",
  "key_findings": ["Ключевой инсайт 1", "Ключевой инсайт 2", "Ключевой инсайт 3"]
}}
"""
        response_text = cls._call_gemini(prompt, gemini_api_key, max_tokens=2048, temperature=0.3)
        if response_text:
            try:
                clean_json = re.sub(r"^```(?:json)?\s*", "", response_text.strip())
                clean_json = re.sub(r"\s*```$", "", clean_json)
                return json.loads(clean_json)
            except Exception as e:
                logger.warning(f"Failed to parse ask_analyst JSON: {e}")
                return {"answer": response_text, "key_findings": []}

        return {
            "answer": "Не удалось получить ответ от Gemini API. Проверьте актуальность вашего API-ключа.",
            "key_findings": []
        }

    @staticmethod
    def _rule_based_explanation(video_data: Dict[str, Any], target_language: str) -> Dict[str, Any]:
        title = video_data.get("title", "")
        ch_title = video_data.get("channel_title", "Channel")
        views = video_data.get("view_count", 0)
        avg = int(video_data.get("channel_avg_views") or views)
        outlier = video_data.get("outlier_score", 1.0)
        vph = video_data.get("velocity_vph", 0.0)

        return {
            "verdict": f"Ролик «{title}» ({ch_title}) набрал {views:,} просмотров ({outlier}x от нормы канала {avg:,}). Высокий темп и вовлеченность позволили ролику занять лидирующие позиции.",
            "hook_analysis": "Заголовок четко бьет в актуальную проблему целевой аудитории с сильной интригой.",
            "trend_alignment": "Тематика попала в актуальный поисковый интерес пользователей.",
            "engagement_factor": f"Темп набора составляет {vph} просмотров в час при стабильном отклике аудитории.",
            "actionable_takeaway": "Снимите ролик-ответ или разбор похожей темы с фокусом на практическую пользу в заголовке."
        }

    @staticmethod
    def _rule_based_daily_digest(
        set_name: str,
        channels_summary: List[Dict[str, Any]],
        top_videos: List[Dict[str, Any]],
        anomalies: List[str],
        target_language: str
    ) -> str:
        lines = [
            f"📢 **Дайджест YouTube Analytics: {set_name}**\n",
            f"• Отслеживается каналов: **{len(channels_summary)}**",
            f"• Статус сбора метрик: **Успешно**\n"
        ]
        if top_videos:
            best = top_videos[0]
            lines.append("🔥 **Главный прорыв:**")
            lines.append(f"• «{best.get('title')}» ({best.get('channel_title')})")
            lines.append(f"  Просмотры: **{best.get('view_count', 0):,}** | Темп: **{int(best.get('velocity_vph', 0))} просм/ч** | Outlier: **{best.get('outlier_score', 1.0)}x**\n")

        if anomalies:
            lines.append("⚡ **Аномалии роста:**")
            for a in anomalies[:3]:
                lines.append(f"• {a}")
            lines.append("")

        lines.append("💡 **Совет:** Публикуйте ролики по горячим инфоповодам в первые 24-48 часов.")
        return "\n".join(lines)
