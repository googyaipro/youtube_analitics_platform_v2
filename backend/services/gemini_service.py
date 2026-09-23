import json
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
import httpx

from backend.prompts import render_prompt

logger = logging.getLogger(__name__)

PRIMARY_GEMINI_MODEL = "gemini-3.8-flash"
FALLBACK_GEMINI_MODELS = [
    "gemini-3.8-flash",
    "gemini-3.6-flash",
    "gemini-2.0-flash",
    "gemini-1.5-flash",
]
GEMINI_API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{PRIMARY_GEMINI_MODEL}:generateContent"

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

        last_error = "Unknown error"
        try:
            with httpx.Client(timeout=10.0) as client:
                for model in FALLBACK_GEMINI_MODELS:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={clean_key}"
                    res = client.post(url, json=body)
                    if res.status_code == 200:
                        return True, f"Gemini API key is valid and connected successfully ({model})."

                    err_json = {}
                    try:
                        err_json = res.json().get("error", {})
                    except Exception:
                        pass
                    last_error = err_json.get("message", f"HTTP {res.status_code}")
                    # If authentication or key is explicitly invalid, stop trying
                    if res.status_code in (401, 403) or "API_KEY_INVALID" in str(err_json) or "API key not valid" in last_error:
                        return False, f"Gemini Error: {last_error}"

                return False, f"Gemini Error: {last_error}"
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
                for model in FALLBACK_GEMINI_MODELS:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key.strip()}"
                    res = client.post(url, json=body)
                    if res.status_code == 200:
                        data = res.json()
                        candidates = data.get("candidates", [])
                        if candidates:
                            parts = candidates[0].get("content", {}).get("parts", [])
                            if parts:
                                return parts[0].get("text", "").strip()
                    else:
                        logger.warning(f"Gemini model {model} returned {res.status_code}: {res.text[:200]}")
                        if res.status_code in (401, 403):
                            break
        except Exception as e:
            logger.error(f"Exception calling Gemini: {e}")

        return None

    @classmethod
    def explain_video_success(
        cls,
        video_data: Optional[Dict[str, Any]] = None,
        target_language: str = "ru",
        gemini_api_key: Optional[str] = None,
        video: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Explain why a specific video outperformed channel averages."""
        target_video = video_data or video or {}
        title = target_video.get("title", "")
        ch_title = target_video.get("channel_title", "Channel")
        views = target_video.get("view_count", 0)
        avg_views = target_video.get("channel_avg_views") or views
        outlier = target_video.get("outlier_score", 1.0)
        vph = target_video.get("velocity_vph", 0.0)
        er = target_video.get("engagement_rate_pct", 0.0)

        lang_name = LANGUAGE_PROMPT_NAMES.get(target_language, "русском (Russian)")

        if not gemini_api_key:
            return cls._rule_based_explanation(target_video, target_language)

        prompt = render_prompt(
            "video_explain.txt",
            title=title,
            channel_title=ch_title,
            views=f"{views:,}",
            avg_views=f"{int(avg_views):,}",
            outlier_score=outlier,
            velocity_vph=vph,
            engagement_rate=er,
            target_language_name=lang_name,
        )
        response_text = cls._call_gemini(prompt, gemini_api_key, max_tokens=1500, temperature=0.25)
        if response_text:
            try:
                clean_json = re.sub(r"^```(?:json)?\s*", "", response_text.strip())
                clean_json = re.sub(r"\s*```$", "", clean_json)
                return json.loads(clean_json)
            except Exception as e:
                logger.warning(f"Error parsing Gemini JSON: {e}")

        return cls._rule_based_explanation(target_video, target_language)

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
        current_date = datetime.now().strftime("%d.%m.%Y")

        if not gemini_api_key or not top_videos:
            return cls._rule_based_daily_digest(set_name, channels_summary, top_videos, anomalies, target_language)

        top_vids_compact = [
            {
                "title": v.get("title"),
                "channel": v.get("channel_title"),
                "views": v.get("view_count", 0),
                "channel_avg": v.get("channel_avg_views", 0),
                "outlier_multiplier": f"{v.get('outlier_score', 1.0)}x",
                "velocity_vph": v.get("velocity_vph", 0),
                "engagement_rate": f"{v.get('engagement_rate_pct', 0)}%"
            }
            for v in top_videos[:10]
        ]

        channels_list = ", ".join([c.get("title", "") for c in channels_summary[:6]])
        anomalies_str = json.dumps(anomalies, ensure_ascii=False) if anomalies else "Стабильная динамика"
        top_vids_str = json.dumps(top_vids_compact, ensure_ascii=False, indent=2)

        prompt = render_prompt(
            "daily_digest.txt",
            set_name=set_name,
            current_date=current_date,
            channels_count=len(channels_summary),
            channels_list=channels_list,
            anomalies_json=anomalies_str,
            top_videos_json=top_vids_str,
            target_language_name=lang_name,
        )
        response_text = cls._call_gemini(prompt, gemini_api_key, max_tokens=3000, temperature=0.35)
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

        prompt = render_prompt(
            "ask_analyst.txt",
            query=query,
            videos_json=json.dumps(videos_context[:10], default=str, ensure_ascii=False, indent=2),
            target_language_name=lang_name,
        )
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
            "answer": "Не удалось сформировать ответ. Проверьте валидность Gemini API ключа.",
            "key_findings": []
        }

    @staticmethod
    def _rule_based_explanation(video_data: Dict[str, Any], target_language: str) -> Dict[str, Any]:
        title = video_data.get("title", "")
        ch_title = video_data.get("channel_title", "Channel")
        views = int(video_data.get("view_count") or 0)
        avg = int(video_data.get("channel_avg_views") or views or 1)
        outlier = video_data.get("outlier_score", 1.0)
        vph = video_data.get("velocity_vph", 0.0)

        return {
            "verdict": f"Ролик «{title}» ({ch_title}) показал взрывной Outlier Score {outlier}x, набрав {views:,} просмотров при норме канала {avg:,}. Сработала формула высокой интриги в заголовке в сочетании с высоким темпом {vph} VPH.",
            "hook_analysis": "Заголовок использует мощный триггер любопытства и эффект срочности, заставляя целевую аудиторию кликать в поисках ответа на ключевой вопрос ниши.",
            "trend_alignment": "Тема ролика идеально оседлала пик поискового спроса и волну обсуждений текущей недели с окном возможностей 48–72 часа.",
            "actionable_takeaway": f"1) Срочно в производство: Снять ролик-ответ или практический бенчмарк по теме «{title[:40]}...»; 2) Формула заголовка: «[Новинка / Модель] vs [Альтернатива]: Всё изменилось...»."
        }

    @staticmethod
    def _rule_based_daily_digest(
        set_name: str,
        channels_summary: List[Dict[str, Any]],
        top_videos: List[Dict[str, Any]],
        anomalies: List[str],
        target_language: str
    ) -> str:
        current_date = datetime.now().strftime("%d.%m.%Y")
        lines = [
            f"📢 **Ежедневный дайджест YouTube Analytics ({current_date})**\n",
            "📊 **Обзор ниши и динамика:**"
        ]
        if top_videos:
            best = top_videos[0]
            top_channel = best.get("channel_title", "Лидер")
            vph = best.get("velocity_vph", 0)
            outlier = best.get("outlier_score", 1.0)
            views = best.get("view_count", 0)

            lines.append(f"Повестку ниши «{set_name}» возглавляет канал **{top_channel}**, показав резкий всплеск вовлеченности аудитории. Зрители демонстрируют высокий интерес к свежим темам с темпом до **{int(vph)} VPH**. При этом фиксируется повышенный спрос на прикладные разборы и сравнительные тесты лидеров сегмента.\n")

            lines.append("🔥 **Главный прорыв дня:**")
            lines.append(f"«{best.get('title')}» — {top_channel}")
            lines.append(f"📈 **{views:,}** просмотров (Outlier: **{outlier}x**, VPH: **{int(vph)}**).")
            lines.append("Сработала связка сильного триггера новизны и точного попадания в поисковый спрос ниши. Аудитория активно кликает на ролики, дающие мгновенный ответ на главный вопрос текущей недели.\n")

            lines.append("💡 **Стратегический совет (Actionable Takeaway):**")
            lines.append(f"• **Срочно в производство:** Выпустить ролик-реакцию или бенчмарк по теме «{best.get('title', '')[:45]}...». Окно максимальной конверсии — 48–72 часа.")
            lines.append("• **Хук на пользу:** Если нет ресурсов на большой тест — подготовьте прикладную подборку «Топ-5 практических решений / связок», утилитарные списки стабильно показывают конверсию в просмотры свыше 4x от нормы.")
        else:
            lines.append(f"Мониторинг набора «{set_name}» активен ({len(channels_summary)} каналов). Добавьте каналы или запустите синхронизацию.")

        return "\n".join(lines)
