import json
import logging
import re
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
import httpx
from sqlalchemy.orm import Session

from backend.prompts import render_prompt
from backend.services.log_service import LogService
from config.settings import get_settings

logger = logging.getLogger(__name__)

PRIMARY_GEMINI_MODEL = "gemini-flash-latest"
FALLBACK_GEMINI_MODELS = [
    "gemini-flash-latest",
    "gemini-3.8-flash",
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
    _discovered_models: Dict[str, str] = {}

    @classmethod
    def verify_api_key(
        cls,
        api_key: Optional[str],
        user_id: Optional[str] = None,
        user_email: Optional[str] = None,
        db: Optional[Session] = None
    ) -> Tuple[bool, str]:
        """Test Gemini API key validity prioritizing gemini-flash-latest with audit logging."""
        start_t = time.perf_counter()
        if not api_key or len(api_key.strip()) < 10:
            msg = "Gemini API key is empty or too short."
            LogService.log_ai_call(
                operation="verify_key",
                model=PRIMARY_GEMINI_MODEL,
                status="ERROR",
                latency_ms=0,
                user_id=user_id,
                user_email=user_email,
                prompt="Verify API Key (length validation)",
                raw_response=msg,
                error_message=msg,
                db=db
            )
            return False, msg

        clean_key = api_key.strip()
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": clean_key,
            "X-goog-api-key": clean_key
        }
        body = {
            "contents": [{"role": "user", "parts": [{"text": "Reply with 'OK'."}]}],
            "generationConfig": {"maxOutputTokens": 10}
        }

        try:
            with httpx.Client(timeout=15.0) as client:
                last_error = "Unknown error"
                last_status = None
                target_models = [
                    "gemini-flash-latest",
                    "gemini-3.8-flash",
                    "gemini-3.8-flash-preview"
                ]
                for model in target_models:
                    for ver in ["v1beta", "v1"]:
                        test_url = f"https://generativelanguage.googleapis.com/{ver}/models/{model}:generateContent?key={clean_key}"
                        try:
                            res = client.post(test_url, json=body, headers=headers)
                            last_status = res.status_code
                            latency_ms = int((time.perf_counter() - start_t) * 1000)
                            if res.status_code == 200:
                                cls._discovered_models[clean_key] = model
                                logger.info(f"Gemini key verified successfully with {model} ({ver})")
                                succ_msg = f"Gemini API key is valid and connected successfully ({model})."
                                LogService.log_ai_call(
                                    operation="verify_key",
                                    model=model,
                                    status="SUCCESS",
                                    latency_ms=latency_ms,
                                    http_status=200,
                                    user_id=user_id,
                                    user_email=user_email,
                                    prompt="Reply with 'OK'.",
                                    raw_response=res.text[:200],
                                    db=db
                                )
                                return True, succ_msg
                            else:
                                try:
                                    last_error = res.json().get("error", {}).get("message", f"HTTP {res.status_code}")
                                except Exception:
                                    last_error = f"HTTP {res.status_code}"
                        except Exception as ex:
                            last_error = str(ex)

                latency_ms = int((time.perf_counter() - start_t) * 1000)
                err_msg = f"Gemini Error: {last_error}"
                LogService.log_ai_call(
                    operation="verify_key",
                    model=PRIMARY_GEMINI_MODEL,
                    status="ERROR",
                    latency_ms=latency_ms,
                    http_status=last_status,
                    user_id=user_id,
                    user_email=user_email,
                    prompt="Reply with 'OK'.",
                    raw_response=last_error,
                    error_message=err_msg,
                    db=db
                )
                return False, err_msg
        except Exception as e:
            latency_ms = int((time.perf_counter() - start_t) * 1000)
            err_msg = f"Network error connecting to Gemini API: {e}"
            logger.error(err_msg)
            LogService.log_ai_call(
                operation="verify_key",
                model=PRIMARY_GEMINI_MODEL,
                status="ERROR",
                latency_ms=latency_ms,
                user_id=user_id,
                user_email=user_email,
                prompt="Reply with 'OK'.",
                raw_response=str(e),
                error_message=err_msg,
                db=db
            )
            return False, err_msg

    @classmethod
    def call_gemini_diagnostics(
        cls,
        prompt: str,
        api_key: str,
        max_tokens: int = 2048,
        temperature: float = 0.4,
        is_json: bool = False
    ) -> Dict[str, Any]:
        """
        Direct HTTP call prioritizing gemini-flash-latest with detailed diagnostic telemetry.
        Returns a dict containing:
        success, text, model, endpoint, http_status, latency_ms, error, raw_json
        """
        if not api_key:
            return {
                "success": False,
                "text": None,
                "model": PRIMARY_GEMINI_MODEL,
                "endpoint": "",
                "http_status": None,
                "latency_ms": 0,
                "error": "No Gemini API key provided",
                "raw_json": None
            }

        clean_key = api_key.strip()
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": clean_key,
            "X-goog-api-key": clean_key
        }

        gen_config: Dict[str, Any] = {
            "temperature": temperature,
            "maxOutputTokens": max_tokens
        }
        if is_json:
            gen_config["responseMimeType"] = "application/json"

        body = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": gen_config
        }

        endpoints = [
            f"https://generativelanguage.googleapis.com/v1beta/models/{PRIMARY_GEMINI_MODEL}:generateContent?key={clean_key}",
            f"https://generativelanguage.googleapis.com/v1/models/{PRIMARY_GEMINI_MODEL}:generateContent?key={clean_key}",
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent?key={clean_key}",
            f"https://generativelanguage.googleapis.com/v1/models/gemini-3.8-flash:generateContent?key={clean_key}",
        ]

        try:
            settings = get_settings()
            if settings.GCP_PROJECT_ID:
                v_region = settings.VERTEX_AI_REGION or "us"
                v_model = settings.GEMINI_MODEL or PRIMARY_GEMINI_MODEL
                vertex_url = f"https://aiplatform.googleapis.com/v1/projects/{settings.GCP_PROJECT_ID}/locations/{v_region}/publishers/google/models/{v_model}:generateContent?key={clean_key}"
                if vertex_url not in endpoints:
                    endpoints.append(vertex_url)
        except Exception as e:
            logger.debug(f"Could not load GCP project settings: {e}")

        cached_model = cls._discovered_models.get(clean_key)
        if cached_model:
            for ver in ["v1beta", "v1"]:
                u = f"https://generativelanguage.googleapis.com/{ver}/models/{cached_model}:generateContent?key={clean_key}"
                if u not in endpoints:
                    endpoints.append(u)

        start_time = time.perf_counter()
        last_error = "Unknown error"
        last_status = None
        last_endpoint = endpoints[0].split("?")[0]
        detected_model = PRIMARY_GEMINI_MODEL

        try:
            with httpx.Client(timeout=35.0) as client:
                for url in endpoints:
                    sanitized_url = url.split("?")[0]
                    last_endpoint = sanitized_url
                    for m in ["gemini-flash-latest", "gemini-3.8-flash", "gemini-3.8-flash-preview"]:
                        if m in sanitized_url:
                            detected_model = m
                            break

                    try:
                        res = client.post(url, json=body, headers=headers)
                        last_status = res.status_code
                        if res.status_code == 200:
                            latency_ms = int((time.perf_counter() - start_time) * 1000)
                            data = res.json()
                            candidates = data.get("candidates", [])
                            if candidates:
                                parts = candidates[0].get("content", {}).get("parts", [])
                                if parts:
                                    text = parts[0].get("text", "").strip()
                                    return {
                                        "success": True,
                                        "text": text,
                                        "model": detected_model,
                                        "endpoint": sanitized_url,
                                        "http_status": 200,
                                        "latency_ms": latency_ms,
                                        "error": None,
                                        "raw_json": data
                                    }
                            last_error = f"200 OK received but no candidate parts (filtered): {data}"
                        else:
                            # If 400 Bad Request with responseMimeType, retry without responseMimeType
                            if res.status_code == 400 and is_json and "responseMimeType" in body["generationConfig"]:
                                alt_body = dict(body)
                                alt_body["generationConfig"] = {k: v for k, v in body["generationConfig"].items() if k != "responseMimeType"}
                                alt_res = client.post(url, json=alt_body, headers=headers)
                                if alt_res.status_code == 200:
                                    latency_ms = int((time.perf_counter() - start_time) * 1000)
                                    data = alt_res.json()
                                    candidates = data.get("candidates", [])
                                    if candidates:
                                        parts = candidates[0].get("content", {}).get("parts", [])
                                        if parts:
                                            return {
                                                "success": True,
                                                "text": parts[0].get("text", "").strip(),
                                                "model": detected_model,
                                                "endpoint": sanitized_url,
                                                "http_status": 200,
                                                "latency_ms": latency_ms,
                                                "error": None,
                                                "raw_json": data
                                            }
                            try:
                                err_data = res.json()
                                last_error = err_data.get("error", {}).get("message", res.text[:200])
                            except Exception:
                                last_error = res.text[:200]
                            logger.warning(f"Gemini call to {sanitized_url} returned {res.status_code}: {last_error}")
                    except Exception as err:
                        last_error = str(err)
                        logger.warning(f"Error calling {sanitized_url}: {err}")
        except Exception as e:
            last_error = str(e)
            logger.error(f"Exception calling Gemini: {e}")

        latency_ms = int((time.perf_counter() - start_time) * 1000)
        return {
            "success": False,
            "text": None,
            "model": detected_model,
            "endpoint": last_endpoint,
            "http_status": last_status,
            "latency_ms": latency_ms,
            "error": last_error,
            "raw_json": None
        }

    @classmethod
    def _call_gemini(cls, prompt: str, api_key: str, max_tokens: int = 2048, temperature: float = 0.4) -> Optional[str]:
        """Direct HTTP call prioritizing gemini-flash-latest via Google AI Studio and Vertex AI."""
        diag = cls.call_gemini_diagnostics(prompt, api_key, max_tokens=max_tokens, temperature=temperature)
        return diag.get("text")

    @staticmethod
    def _parse_explain_response(text: Optional[str]) -> Tuple[Optional[Dict[str, Any]], str]:
        """Resiliently parse Gemini breakdown into structured dict."""
        if not text or not text.strip():
            return None, "empty_text"

        clean = text.strip()
        clean = re.sub(r"^```(?:json)?\s*", "", clean)
        clean = re.sub(r"\s*```$", "", clean)
        clean = clean.strip()

        # 1. Standard json.loads
        try:
            parsed = json.loads(clean)
            if isinstance(parsed, dict) and any(k in parsed for k in ("verdict", "hook_analysis", "trend_alignment", "actionable_takeaway")):
                return parsed, "json_loads"
        except Exception:
            pass

        # 2. Search outermost braces
        m = re.search(r"\{.*\}", clean, re.DOTALL)
        if m:
            try:
                parsed = json.loads(m.group(0))
                if isinstance(parsed, dict) and any(k in parsed for k in ("verdict", "hook_analysis", "trend_alignment", "actionable_takeaway")):
                    return parsed, "outermost_braces"
            except Exception:
                pass

        # 3. Regex key extraction
        keys = ["verdict", "hook_analysis", "trend_alignment", "actionable_takeaway"]
        extracted: Dict[str, Any] = {}
        for k in keys:
            pattern = r'["\']?' + k + r'["\']?\s*:\s*["\']([\s\S]*?)(?=["\']\s*,\s*["\']?(?:verdict|hook_analysis|trend_alignment|actionable_takeaway)["\']?\s*:|\s*["\']\s*\}|$)'
            km = re.search(pattern, clean)
            if km:
                val = km.group(1).replace('\\"', '"').replace('\\n', '\n').strip().rstrip('"').rstrip("'")
                extracted[k] = val

        if len(extracted) >= 2:
            return extracted, "regex_keys"

        # 4. Heading or freeform text fallback
        if len(clean) > 30:
            return {
                "verdict": clean[:1200],
                "hook_analysis": "Детальный психологический разбор включен в вердикт выше.",
                "trend_alignment": "Анализ макро-тренда и вовлеченности включен в вердикт выше.",
                "actionable_takeaway": "Рекомендации по производству включены в вердикт выше."
            }, "text_fallback"

        return None, "unparseable"

    @classmethod
    def explain_video_success(
        cls,
        video_data: Optional[Dict[str, Any]] = None,
        target_language: str = "ru",
        gemini_api_key: Optional[str] = None,
        video: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None,
        user_email: Optional[str] = None,
        db: Optional[Session] = None
    ) -> Dict[str, Any]:
        """Explain why a specific video outperformed channel averages with full telemetry."""
        target_video = video_data or video or {}
        title = target_video.get("title", "")
        ch_title = target_video.get("channel_title", "Channel")
        views = target_video.get("view_count", 0)
        avg_views = target_video.get("channel_avg_views") or views
        outlier = target_video.get("outlier_score", 1.0)
        vph = target_video.get("velocity_vph", 0.0)
        er = target_video.get("engagement_rate_pct", 0.0)

        subs = target_video.get("subscriber_count", 0)
        subs_str = f"{subs:,}" if subs else "Не указано"
        format_type = "Shorts 📱" if target_video.get("is_short") else "Long-form 🎬"
        dur_fmt = target_video.get("duration_formatted", "--:--")
        views_to_subs = target_video.get("views_to_subs_pct", 0.0)
        pub_at = str(target_video.get("published_at", ""))[:19]
        desc = (target_video.get("description") or "")[:400]

        lang_name = LANGUAGE_PROMPT_NAMES.get(target_language, "русском (Russian)")

        if not gemini_api_key:
            try:
                settings = get_settings()
                gemini_api_key = getattr(settings, "GEMINI_API_KEY", None)
            except Exception:
                pass

        if not gemini_api_key:
            res = cls._rule_based_explanation(target_video, target_language)
            res["is_ai"] = False
            res["fallback_reason"] = "Ключ Gemini API не настроен в Профиле или переменных окружения"
            LogService.log_ai_call(
                operation="explain_video",
                model=PRIMARY_GEMINI_MODEL,
                status="FALLBACK_RULE_BASED",
                latency_ms=0,
                user_id=user_id,
                user_email=user_email,
                target_id=target_video.get("video_id"),
                target_title=title,
                prompt="No Gemini key provided - generated heuristic fallback",
                raw_response="Fallback: Heuristic rule-based explanation",
                parsed_output=res,
                fallback_reason=res["fallback_reason"],
                db=db
            )
            return res

        prompt = render_prompt(
            "video_explain.txt",
            title=title,
            channel_title=ch_title,
            subscriber_count=subs_str,
            format_type=format_type,
            duration_formatted=dur_fmt,
            published_at=pub_at,
            views=f"{views:,}",
            avg_views=f"{int(avg_views):,}",
            outlier_score=outlier,
            views_to_subs_pct=views_to_subs,
            velocity_vph=vph,
            engagement_rate=er,
            description_snippet=desc or "Нет описания",
            target_language_name=lang_name,
        )

        diag = cls.call_gemini_diagnostics(prompt, gemini_api_key, max_tokens=2000, temperature=0.25, is_json=True)

        if diag["success"] and diag["text"]:
            parsed, parse_method = cls._parse_explain_response(diag["text"])
            if parsed:
                parsed["is_ai"] = True
                parsed["model"] = diag["model"]
                parsed["latency_ms"] = diag["latency_ms"]
                parsed["parse_method"] = parse_method
                parsed["prompt_used"] = prompt
                parsed["raw_response"] = diag["text"]

                log_status = "SUCCESS" if parse_method in ("json_loads", "outermost_braces") else "PARSE_ERROR_RECOVERED"
                LogService.log_ai_call(
                    operation="explain_video",
                    model=diag["model"],
                    status=log_status,
                    latency_ms=diag["latency_ms"],
                    user_id=user_id,
                    user_email=user_email,
                    target_id=target_video.get("video_id"),
                    target_title=title,
                    prompt=prompt,
                    raw_response=diag["text"],
                    parsed_output=parsed,
                    http_status=200,
                    fallback_reason=f"Parsed using {parse_method}" if parse_method != "json_loads" else None,
                    db=db
                )
                return parsed

            # If text could not be parsed at all
            res = cls._rule_based_explanation(target_video, target_language)
            res["is_ai"] = False
            res["fallback_reason"] = "Ответ модели не удалось разобрать как структуру"
            res["prompt_used"] = prompt
            res["raw_response"] = diag["text"]
            LogService.log_ai_call(
                operation="explain_video",
                model=diag["model"],
                status="PARSE_ERROR",
                latency_ms=diag["latency_ms"],
                user_id=user_id,
                user_email=user_email,
                target_id=target_video.get("video_id"),
                target_title=title,
                prompt=prompt,
                raw_response=diag["text"],
                parsed_output=res,
                http_status=diag.get("http_status"),
                fallback_reason="Failed to parse model response into fields",
                db=db
            )
            return res

        # If call failed (HTTP error, connection error, etc.)
        res = cls._rule_based_explanation(target_video, target_language)
        res["is_ai"] = False
        err_msg = diag.get("error") or "Сбой вызова Gemini API"
        res["fallback_reason"] = f"Ошибка Gemini: {err_msg}"
        res["prompt_used"] = prompt
        res["raw_response"] = diag.get("error")
        LogService.log_ai_call(
            operation="explain_video",
            model=diag["model"],
            status="ERROR",
            latency_ms=diag["latency_ms"],
            user_id=user_id,
            user_email=user_email,
            target_id=target_video.get("video_id"),
            target_title=title,
            prompt=prompt,
            raw_response=diag.get("error"),
            parsed_output=res,
            http_status=diag.get("http_status"),
            error_message=err_msg,
            fallback_reason=f"API error: {err_msg}",
            db=db
        )
        return res

    @classmethod
    def generate_daily_digest(
        cls,
        set_name: str,
        channels_summary: List[Dict[str, Any]],
        top_videos: List[Dict[str, Any]],
        anomalies: List[str],
        target_language: str = "ru",
        gemini_api_key: Optional[str] = None,
        user_id: Optional[str] = None,
        user_email: Optional[str] = None,
        db: Optional[Session] = None
    ) -> str:
        """Generate executive AI daily digest tailored to user's channel set and language."""
        lang_name = LANGUAGE_PROMPT_NAMES.get(target_language, "русском (Russian)")
        current_date = datetime.now().strftime("%d.%m.%Y")

        if not gemini_api_key:
            try:
                settings = get_settings()
                gemini_api_key = getattr(settings, "GEMINI_API_KEY", None)
            except Exception:
                pass

        if not gemini_api_key or not top_videos:
            return cls._rule_based_daily_digest(set_name, channels_summary, top_videos, anomalies, target_language)

        top_vids_compact = [
            {
                "title": v.get("title"),
                "channel": v.get("channel_title"),
                "channel_subs": f"{v.get('subscriber_count', 0):,}" if v.get("subscriber_count") else ("Н/Д" if target_language == "ru" else "N/A"),
                "format": "Shorts" if v.get("is_short") else f"Video ({v.get('duration_formatted', '--:--')})",
                "views": f"{v.get('view_count', 0):,}",
                "channel_norm": f"{v.get('channel_avg_views', 0):,}",
                "outlier_multiplier": f"{v.get('outlier_score', 1.0)}x",
                "velocity_vph": f"{v.get('velocity_vph', 0)} VPH",
                "views_to_subs": f"{v.get('views_to_subs_pct', 0.0)}%",
                "engagement_rate": f"{v.get('engagement_rate_pct', 0)}%"
            }
            for v in top_videos[:12]
        ]

        channels_list = ", ".join([c.get("title", "") for c in channels_summary[:6]])
        anomalies_str = json.dumps(anomalies, ensure_ascii=False) if anomalies else "Стабильная динамика"
        top_vids_str = json.dumps(top_vids_compact, ensure_ascii=False, indent=2)

        headers_dict = {
            "ru": {
                "header_title": f"📢 Ежедневный дайджест YouTube Analytics ({current_date})",
                "header_overview": "📊 Обзор ниши и динамика:",
                "header_breakthrough": "🔥 Главный прорыв дня:",
                "header_anomaly": "⚡ Аномалия охвата (Давид против Голиафа):",
                "header_actionable": "💡 Стратегический совет и Контентные дыры (Actionable Takeaway):",
                "bullet_urgent": "• Срочно в производство:",
                "bullet_gap": "• Контентная дыра (Content Gap):",
                "bullet_utility": "• Хук на пользу:",
            },
            "en": {
                "header_title": f"📢 YouTube Analytics Daily Digest ({current_date})",
                "header_overview": "📊 Niche Overview & Dynamics:",
                "header_breakthrough": "🔥 Main Breakthrough of the Day:",
                "header_anomaly": "⚡ Reach Anomaly (David vs Goliath):",
                "header_actionable": "💡 Strategic Advice & Content Gaps (Actionable Takeaway):",
                "bullet_urgent": "• Immediate Production Priority:",
                "bullet_gap": "• Content Gap:",
                "bullet_utility": "• High-Utility Hook:",
            },
            "de": {
                "header_title": f"📢 YouTube Analytics Täglicher Digest ({current_date})",
                "header_overview": "📊 Nischenübersicht & Dynamik:",
                "header_breakthrough": "🔥 Hauptdurchbruch des Tages:",
                "header_anomaly": "⚡ Reichweiten-Anomalie (David gegen Goliath):",
                "header_actionable": "💡 Strategische Ratschläge & Content-Lücken (Actionable Takeaway):",
                "bullet_urgent": "• Dringend in die Produktion:",
                "bullet_gap": "• Content-Lücke (Content Gap):",
                "bullet_utility": "• Nutzen-Hook:",
            },
            "fi": {
                "header_title": f"📢 YouTube Analytics Päivittäinen Yhteenveto ({current_date})",
                "header_overview": "📊 Nichen yleiskatsaus ja dynamiikka:",
                "header_breakthrough": "🔥 Päivän suurin läpimurto:",
                "header_anomaly": "⚡ Kattavuusanomalia (Daavid vastaan Goljat):",
                "header_actionable": "💡 Strateginen neuvonta ja sisältöaukot (Actionable Takeaway):",
                "bullet_urgent": "• Kiireellisesti tuotantoon:",
                "bullet_gap": "• Sisältöaukko (Content Gap):",
                "bullet_utility": "• Hyötykoukku:",
            },
            "ka": {
                "header_title": f"📢 YouTube Analytics ყოველდღიური დაიჯესტი ({current_date})",
                "header_overview": "📊 ნიშის მიმოხილვა და დინამიკა:",
                "header_breakthrough": "🔥 დღის მთავარი გარღვევა:",
                "header_anomaly": "⚡ წვდომის ანომალია (დავითი გოლიათის წინააღმდეგ):",
                "header_actionable": "💡 სტრატეგიული რჩევა და კონტენტის ხარვეზები (Actionable Takeaway):",
                "bullet_urgent": "• სასწრაფოდ წარმოებაში:",
                "bullet_gap": "• კონტენტის ხარვეზი (Content Gap):",
                "bullet_utility": "• სასარგებლო ჰუკი:",
            }
        }
        hdrs = headers_dict.get(target_language) or headers_dict.get("en") or headers_dict["ru"]

        prompt = render_prompt(
            "daily_digest.txt",
            set_name=set_name,
            current_date=current_date,
            channels_count=len(channels_summary),
            channels_list=channels_list,
            anomalies_json=anomalies_str,
            top_videos_json=top_vids_str,
            target_language_name=lang_name,
            header_title=hdrs["header_title"],
            header_overview=hdrs["header_overview"],
            header_breakthrough=hdrs["header_breakthrough"],
            header_anomaly=hdrs["header_anomaly"],
            header_actionable=hdrs["header_actionable"],
            bullet_urgent=hdrs["bullet_urgent"],
            bullet_gap=hdrs["bullet_gap"],
            bullet_utility=hdrs["bullet_utility"],
        )
        diag = cls.call_gemini_diagnostics(prompt, gemini_api_key, max_tokens=3000, temperature=0.35)
        if diag["success"] and diag["text"]:
            LogService.log_ai_call(
                operation="daily_digest",
                model=diag["model"],
                status="SUCCESS",
                latency_ms=diag["latency_ms"],
                user_id=user_id,
                user_email=user_email,
                target_id=set_name,
                target_title=f"Digest: {set_name}",
                prompt=prompt,
                raw_response=diag["text"],
                http_status=200,
                db=db
            )
            return diag["text"]

        res = cls._rule_based_daily_digest(set_name, channels_summary, top_videos, anomalies, target_language)
        err_msg = diag.get("error") if gemini_api_key else "No Gemini API key provided"
        LogService.log_ai_call(
            operation="daily_digest",
            model=diag.get("model", PRIMARY_GEMINI_MODEL),
            status="FALLBACK_RULE_BASED" if not diag.get("error") else "ERROR",
            latency_ms=diag.get("latency_ms", 0),
            user_id=user_id,
            user_email=user_email,
            target_id=set_name,
            target_title=f"Digest: {set_name}",
            prompt=prompt if gemini_api_key else "No Gemini API key - rule based fallback",
            raw_response=res,
            http_status=diag.get("http_status"),
            error_message=err_msg if diag.get("error") else None,
            fallback_reason=err_msg,
            db=db
        )
        return res

    @classmethod
    def ask_analyst(
        cls,
        query: str,
        videos_context: List[Dict[str, Any]],
        target_language: str = "ru",
        gemini_api_key: Optional[str] = None,
        user_id: Optional[str] = None,
        user_email: Optional[str] = None,
        db: Optional[Session] = None
    ) -> Dict[str, Any]:
        """Interactive Q&A with Gemini regarding channel videos with full telemetry."""
        lang_name = LANGUAGE_PROMPT_NAMES.get(target_language, "русском (Russian)")

        if not gemini_api_key:
            res = {
                "answer": "Для получения персонального AI-анализа укажите ваш Gemini API ключ в настройках профиля.",
                "key_findings": ["Ключ Gemini не настроен"]
            }
            LogService.log_ai_call(
                operation="ask_analyst",
                model=PRIMARY_GEMINI_MODEL,
                status="ERROR",
                latency_ms=0,
                user_id=user_id,
                user_email=user_email,
                target_title=query,
                prompt=query,
                raw_response=res["answer"],
                error_message="Gemini API key is not configured",
                db=db
            )
            return res

        vids_context_compact = [
            {
                "title": v.get("title"),
                "channel": v.get("channel_title"),
                "subs": v.get("subscriber_count", 0),
                "format": "Shorts" if v.get("is_short") else f"Video ({v.get('duration_formatted', '--:--')})",
                "views": v.get("view_count", 0),
                "channel_norm": v.get("channel_avg_views", 0),
                "outlier": f"{v.get('outlier_score', 1.0)}x",
                "vph": v.get("velocity_vph", 0),
                "views_to_subs": f"{v.get('views_to_subs_pct', 0.0)}%",
                "er": f"{v.get('engagement_rate_pct', 0)}%",
                "published_at": str(v.get("published_at", ""))[:10]
            }
            for v in videos_context[:12]
        ]

        prompt = render_prompt(
            "ask_analyst.txt",
            query=query,
            videos_json=json.dumps(vids_context_compact, default=str, ensure_ascii=False, indent=2),
            target_language_name=lang_name,
        )
        diag = cls.call_gemini_diagnostics(prompt, gemini_api_key, max_tokens=2048, temperature=0.3, is_json=True)
        if diag["success"] and diag["text"]:
            parsed = None
            try:
                clean_json = re.sub(r"^```(?:json)?\s*", "", diag["text"].strip())
                clean_json = re.sub(r"\s*```$", "", clean_json)
                parsed = json.loads(clean_json)
            except Exception as e:
                logger.warning(f"Failed to parse ask_analyst JSON: {e}")
                parsed = {"answer": diag["text"], "key_findings": []}

            LogService.log_ai_call(
                operation="ask_analyst",
                model=diag["model"],
                status="SUCCESS",
                latency_ms=diag["latency_ms"],
                user_id=user_id,
                user_email=user_email,
                target_title=query,
                prompt=prompt,
                raw_response=diag["text"],
                parsed_output=parsed,
                http_status=200,
                db=db
            )
            return parsed

        err_msg = diag.get("error") or "Не удалось сформировать ответ. Проверьте валидность Gemini API ключа."
        res = {
            "answer": err_msg,
            "key_findings": []
        }
        LogService.log_ai_call(
            operation="ask_analyst",
            model=diag.get("model", PRIMARY_GEMINI_MODEL),
            status="ERROR",
            latency_ms=diag.get("latency_ms", 0),
            user_id=user_id,
            user_email=user_email,
            target_title=query,
            prompt=prompt,
            raw_response=diag.get("error"),
            http_status=diag.get("http_status"),
            error_message=err_msg,
            db=db
        )
        return res

    @staticmethod
    def _rule_based_explanation(video_data: Dict[str, Any], target_language: str) -> Dict[str, Any]:
        """Objective, non-hyped statistical breakdown when Gemini key is not configured or offline."""
        title = video_data.get("title", "")
        ch_title = video_data.get("channel_title", "Channel")
        views = int(video_data.get("view_count") or 0)
        avg = int(video_data.get("channel_avg_views") or views or 1)
        outlier = float(video_data.get("outlier_score") or 1.0)
        vph = float(video_data.get("velocity_vph") or 0.0)
        er = float(video_data.get("engagement_rate_pct") or 0.0)
        views_to_subs = float(video_data.get("views_to_subs_pct") or 0.0)
        is_short = bool(video_data.get("is_short"))
        dur_str = video_data.get("duration_formatted", "--:--")

        has_question = "?" in title
        has_digits = any(c.isdigit() for c in title)
        title_len = len(title)

        if target_language == "ru":
            if outlier >= 2.0:
                verdict = (
                    f"Ролик «{title}» ({ch_title}) показал результат существенно выше нормы канала: "
                    f"множитель {outlier}x к медиане ({views:,} просмотров против базовых {avg:,}). "
                    f"Текущий темп {vph} VPH указывает на активное привлечение новой аудитории."
                )
            elif outlier >= 1.2:
                verdict = (
                    f"Ролик «{title}» ({ch_title}) превышает средние показатели канала ({outlier}x к норме {avg:,}). "
                    f"Темп прироста: {vph} VPH."
                )
            elif outlier >= 0.8:
                verdict = (
                    f"Показатели ролика «{title}» ({views:,} просмотров) находятся в пределах стандартного диапазона канала "
                    f"({outlier}x от медианы {avg:,}). Темп: {vph} VPH."
                )
            else:
                verdict = (
                    f"Ролик «{title}» набрал {views:,} просмотров, что ниже медианы канала {avg:,} ({outlier}x). "
                    f"Темп прироста: {vph} VPH."
                )

            hook_parts = [f"Формат: {'Shorts' if is_short else 'Видео'} ({dur_str})", f"длина заголовка {title_len} симв."]
            if has_question:
                hook_parts.append("вопросительная конструкция")
            if has_digits:
                hook_parts.append("числовой маркер")
            hook_analysis = f"Структурный анализ: {', '.join(hook_parts)}. Вовлеченность (ER): {er}%."

            trend_alignment = (
                f"Скорость набора: {vph} VPH. "
                f"Охват относительно подписчиков: {views_to_subs}%. "
                f"Активность аудитории (лайки/комментарии): {'выше среднего' if er >= 2.5 else 'в пределах нормы'}."
            )

            actionable_takeaway = (
                f"1) Формат: {'Короткое видео (Shorts)' if is_short else f'Горизонтальное видео ({dur_str})'}; "
                f"2) Для глубокого контентного анализа смысловых триггеров и сценария подключите ключ Gemini в настройках Профиля; "
                f"3) При создании похожих материалов ориентируйтесь на темп {vph} VPH как бенчмарк."
            )
        elif target_language == "de":
            if outlier >= 2.0:
                verdict = (
                    f"Das Video «{title}» ({ch_title}) erzielte ein herausragendes Ergebnis: "
                    f"{outlier}x über dem Kanal-Median ({views:,} Aufrufe vs. Baseline {avg:,}). "
                    f"Die aktuelle Geschwindigkeit von {vph} VPH zeigt eine starke Algorithmus-Empfehlung."
                )
            elif outlier >= 1.2:
                verdict = (
                    f"Das Video «{title}» ({ch_title}) liegt über dem Kanaldurchschnitt ({outlier}x über Baseline {avg:,}). "
                    f"Geschwindigkeit: {vph} VPH."
                )
            elif outlier >= 0.8:
                verdict = (
                    f"Das Video «{title}» ({views:,} Aufrufe) liegt im normalen Kanalbereich "
                    f"({outlier}x des Medians {avg:,}). Geschwindigkeit: {vph} VPH."
                )
            else:
                verdict = (
                    f"Das Video «{title}» erreichte {views:,} Aufrufe, was unter dem Kanal-Median {avg:,} liegt ({outlier}x). "
                    f"Geschwindigkeit: {vph} VPH."
                )

            hook_analysis = (
                f"Format: {'Shorts' if is_short else 'Langvideo'} ({dur_str}), Titellänge: {title_len} Zeichen. "
                f"Engagement-Rate (ER): {er}%."
            )
            trend_alignment = (
                f"Geschwindigkeit: {vph} VPH. Verhältnis Aufrufe zu Abonnenten: {views_to_subs}%. "
                f"Publikumsreaktion: {'hohe Aktivität' if er >= 2.5 else 'im Normalbereich'}."
            )
            actionable_takeaway = (
                f"1) Format: {'Shorts' if is_short else f'Standard-Video ({dur_str})'}; "
                f"2) Für eine tiefe semantische Skript- und Klickraten-Analyse hinterlegen Sie Ihren Gemini-API-Schlüssel im Profil; "
                f"3) Nutzen Sie das Tempo von {vph} VPH als Richtwert für diese Nische."
            )
        elif target_language == "fi":
            if outlier >= 2.0:
                verdict = (
                    f"Video «{title}» ({ch_title}) saavutti läpimurtotuloksen: "
                    f"{outlier}x yli kanavan mediaanin ({views:,} katselukertaa vs. perustaso {avg:,}). "
                    f"Nykyinen nopeus {vph} VPH osoittaa vahvaa suosittelualgoritmin tukea."
                )
            elif outlier >= 1.2:
                verdict = (
                    f"Video «{title}» ({ch_title}) ylittää kanavan keskiarvon ({outlier}x yli perustason {avg:,}). "
                    f"Nopeus: {vph} VPH."
                )
            elif outlier >= 0.8:
                verdict = (
                    f"Video «{title}» ({views:,} katselukertaa) sijoittuu kanavan tavanomaiseen vaihteluväliin "
                    f"({outlier}x mediaanista {avg:,}). Nopeus: {vph} VPH."
                )
            else:
                verdict = (
                    f"Video «{title}» keräsi {views:,} katselukertaa, mikä alittaa kanavan mediaanin {avg:,} ({outlier}x). "
                    f"Nopeus: {vph} VPH."
                )

            hook_analysis = (
                f"Muoto: {'Shorts' if is_short else 'Pitkä video'} ({dur_str}), otsikon pituus: {title_len} merkkiä. "
                f"Sitoutumisaste (ER): {er}%."
            )
            trend_alignment = (
                f"Nopeus: {vph} VPH. Katselujen suhde tilaajiin: {views_to_subs}%. "
                f"Yleisön aktiivisuus: {'korkea sitoutuminen' if er >= 2.5 else 'tavanomainen taso'}."
            )
            actionable_takeaway = (
                f"1) Muoto: {'Shorts' if is_short else f'Perusvideo ({dur_str})'}; "
                f"2) Syvällistä semanttista käsikirjoitus- ja CTR-analyysiä varten liitä Gemini API -avain profiilissasi; "
                f"3) Käytä tämän videon {vph} VPH -nopeutta vertailukohtana tälle nichelle."
            )
        elif target_language == "ka":
            if outlier >= 2.0:
                verdict = (
                    f"ვიდეომ «{title}» ({ch_title}) აჩვენა გარღვევის შედეგი: "
                    f"არხის მედიანაზე {outlier}x მეტი ({views:,} ნახვა საბაზისო {avg:,}-ის წინააღმდეგ). "
                    f"მიმდინარე ტემპი {vph} VPH მიუთითებს ალგორითმის აქტიურ მხარდაჭერაზე."
                )
            elif outlier >= 1.2:
                verdict = (
                    f"ვიდეო «{title}» ({ch_title}) აღემატება არხის საშუალო მაჩვენებელს ({outlier}x ნორმაზე {avg:,}). "
                    f"ტემპი: {vph} VPH."
                )
            elif outlier >= 0.8:
                verdict = (
                    f"ვიდეო «{title}» ({views:,} ნახვა) იმყოფება არხის სტანდარტულ დიაპაზონში "
                    f"({outlier}x მედიანიდან {avg:,}). ტემპი: {vph} VPH."
                )
            else:
                verdict = (
                    f"ვიდეომ «{title}» დააგროვა {views:,} ნახვა, რაც არხის მედიანაზე {avg:,} ნაკლებია ({outlier}x). "
                    f"ტემპი: {vph} VPH."
                )

            hook_analysis = (
                f"ფორმატი: {'Shorts' if is_short else 'ვიდეო'} ({dur_str}), სათაურის სიგრძე: {title_len} სიმბოლო. "
                f"ჩართულობა (ER): {er}%."
            )
            trend_alignment = (
                f"სიჩქარე: {vph} VPH. ნახვების თანაფარდობა გამომწერებთან: {views_to_subs}%. "
                f"აუდიტორიის აქტიურობა: {'მაღალი' if er >= 2.5 else 'სტანდარტული'}."
            )
            actionable_takeaway = (
                f"1) ფორმატი: {'Shorts' if is_short else f'სტანდარტული ვიდეო ({dur_str})'}; "
                f"2) სცენარისა და CTR ფაქტორების ღრმა ანალიზისთვის დააკავშირეთ Gemini API გასაღები პროფილში; "
                f"3) გამოიყენეთ {vph} VPH სიჩქარე, როგორც ორიენტირი ამ ნიშისთვის."
            )
        else:
            if outlier >= 2.0:
                verdict = (
                    f"Video \"{title}\" ({ch_title}) achieved breakout results: "
                    f"{outlier}x over channel median ({views:,} views vs baseline {avg:,}). "
                    f"Current pace of {vph} VPH indicates strong algorithm discovery."
                )
            elif outlier >= 1.2:
                verdict = (
                    f"Video \"{title}\" ({ch_title}) is performing above channel average ({outlier}x over baseline {avg:,}). "
                    f"Pace: {vph} VPH."
                )
            else:
                verdict = (
                    f"Video \"{title}\" ({views:,} views) is tracking within normal channel range "
                    f"({outlier}x of median {avg:,}). Pace: {vph} VPH."
                )

            hook_analysis = (
                f"Format: {'Shorts' if is_short else 'Long-form'} ({dur_str}), title length: {title_len} chars. "
                f"Engagement Rate (ER): {er}%."
            )
            trend_alignment = (
                f"Velocity: {vph} VPH. View-to-subscriber ratio: {views_to_subs}%. "
                f"Audience reaction: {'high engagement' if er >= 2.5 else 'steady baseline'}."
            )
            actionable_takeaway = (
                f"1) Format: {'Shorts' if is_short else f'Standard long-form ({dur_str})'}; "
                f"2) For deep semantic script & CTR factor analysis, connect your Gemini API key in Profile; "
                f"3) Use this video's {vph} VPH velocity as a benchmark for this niche."
            )

        return {
            "verdict": verdict,
            "hook_analysis": hook_analysis,
            "trend_alignment": trend_alignment,
            "actionable_takeaway": actionable_takeaway,
            "is_ai": False
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
        lang = target_language if target_language in ("ru", "en", "de", "fi", "ka") else "en"

        template_map = {
            "ru": {
                "title": f"📢 **Ежедневный дайджест YouTube Analytics ({current_date})**\n",
                "sec_overview": "📊 **Обзор ниши и динамика:**",
                "overview_text": "Повестку ниши «{set_name}» возглавляет канал **{top_channel}**, показав резкий всплеск вовлеченности аудитории. Зрители демонстрируют высокий интерес к свежим темам с темпом до **{vph} VPH**. При этом фиксируется повышенный спрос на прикладные разборы и сравнительные тесты лидеров сегмента.\n",
                "sec_breakthrough": "🔥 **Главный прорыв дня:**",
                "breakthrough_sub": "«{title}» — {channel}\n📈 **{views:,}** просмотров (Outlier: **{outlier}x**, VPH: **{vph}**).\nСработала связка сильного триггера новизны и точного попадания в поисковый спрос ниши. Аудитория активно кликает на ролики, дающие мгновенный ответ на главный вопрос текущей недели.\n",
                "sec_anomaly": "⚡ **Аномалия охвата (Давид против Голиафа):**",
                "anomaly_text": "Канал **{channel}** показал сверхвысокую конверсию в просмотры ({views:,} просм., **{outlier}x** к норме). Алгоритм YouTube активно продвигает ролик в рекомендации (Browse Features).\n",
                "sec_actionable": "💡 **Стратегический совет и Контентные дыры (Actionable Takeaway):**",
                "urgent": "• **Срочно в производство:** Выпустить ролик-реакцию или бенчмарк по теме «{title_short}...». Окно максимальной конверсии — 48–72 часа.",
                "gap": "• **Контентная дыра (Content Gap):** Аудитория ищет прикладные сценарии использования, но большинство авторов выпускают лишь поверхностные обзоры.",
                "utility": "• **Хук на пользу:** Подготовьте подборку «Топ-5 практических решений / связок», утилитарные списки стабильно показывают конверсию в просмотры свыше 4x от нормы.",
                "empty": "Мониторинг набора «{set_name}» активен ({count} каналов). Добавьте каналы или запустите синхронизацию."
            },
            "en": {
                "title": f"📢 **YouTube Analytics Daily Digest ({current_date})**\n",
                "sec_overview": "📊 **Niche Overview & Dynamics:**",
                "overview_text": "The agenda in the \"{set_name}\" niche is led by **{top_channel}**, showing a sharp surge in audience engagement with velocity reaching up to **{vph} VPH**. High viewer interest is focused around practical breakdowns and benchmark tests.\n",
                "sec_breakthrough": "🔥 **Main Breakthrough of the Day:**",
                "breakthrough_sub": "\"{title}\" — {channel}\n📈 **{views:,}** views (Outlier: **{outlier}x**, Velocity: **{vph} VPH**).\nA strong novelty trigger combined with niche search demand drove this performance. The packaging directly answers the audience's most urgent questions.\n",
                "sec_anomaly": "⚡ **Reach Anomaly (David vs Goliath):**",
                "anomaly_text": "Channel **{channel}** achieved massive viral reach ({views:,} views, **{outlier}x** above channel baseline), proving that focused curiosity-gap packaging reliably outperforms channel size.\n",
                "sec_actionable": "💡 **Strategic Advice & Content Gaps (Actionable Takeaway):**",
                "urgent": "• **Immediate Production Priority:** Produce a fast-follow benchmark or tactical reaction to \"{title_short}...\". Peak conversion window is 48–72 hours.",
                "gap": "• **Content Gap:** The niche is saturated with surface-level news, creating a high-demand vacuum for deep practical workflow breakdowns.",
                "utility": "• **High-Utility Hook:** Package a \"Top 5 Battle-Tested Solutions\" breakdown; high-utility lists consistently outperform channel averages by over 4x.",
                "empty": "Tracking active for \"{set_name}\" ({count} channels). Add channels or trigger sync to collect data."
            },
            "de": {
                "title": f"📢 **YouTube Analytics Täglicher Digest ({current_date})**\n",
                "sec_overview": "📊 **Nischenübersicht & Dynamik:**",
                "overview_text": "Die Themen der Nische «{set_name}» werden von **{top_channel}** angeführt, mit einer hohen Wiedergabegeschwindigkeit von bis zu **{vph} VPH**.\n",
                "sec_breakthrough": "🔥 **Hauptdurchbruch des Tages:**",
                "breakthrough_sub": "«{title}» — {channel}\n📈 **{views:,}** Aufrufe (Outlier: **{outlier}x**, VPH: **{vph}**).\nStarke Neuheitsfaktoren und zielgerichtete Verpackung führten zu diesem viralen Ausbruch.\n",
                "sec_anomaly": "⚡ **Reichweiten-Anomalie (David gegen Goliath):**",
                "anomaly_text": "Kanal **{channel}** erzielte herausragende Reichweite ({views:,} Aufrufe, **{outlier}x** über Norm), was die Effektivität von klaren Nutzen-Hooks beweist.\n",
                "sec_actionable": "💡 **Strategische Ratschläge & Content-Lücken (Actionable Takeaway):**",
                "urgent": "• **Dringend in die Produktion:** Schnelles Reaktions- oder Testvideo zum Thema «{title_short}...» veröffentlichen. Zeitfenster: 48–72 Stunden.",
                "gap": "• **Content-Lücke (Content Gap):** Das Publikum sucht nach praxisnahen Schritt-für-Schritt-Anleitungen.",
                "utility": "• **Nutzen-Hook:** Erstellen Sie ein «Top 5 Best Practices»-Format; praktische Listen übertreffen den Kanaldurchschnitt um das 3- bis 4-Fache.",
                "empty": "Überwachung für «{set_name}» aktiv ({count} Kanäle). Fügen Sie Kanäle hinzu oder starten Sie die Synchronisierung."
            },
            "fi": {
                "title": f"📢 **YouTube Analytics Päivittäinen Yhteenveto ({current_date})**\n",
                "sec_overview": "📊 **Nichen yleiskatsaus ja dynamiikka:**",
                "overview_text": "Nichen «{set_name}» kärjessä on kanava **{top_channel}**, joka osoittaa poikkeuksellista sitoutumista ja jopa **{vph} VPH** -nopeutta tuoreille aiheille.\n",
                "sec_breakthrough": "🔥 **Päivän suurin läpimurto:**",
                "breakthrough_sub": "«{title}» — {channel}\n📈 **{views:,}** katselukertaa (Outlier: **{outlier}x**, VPH: **{vph}**).\nUutuusarvon ja tarkan otsikoinnin yhdistelmä laukaisi vahvan algoritmin suositusvirran.\n",
                "sec_anomaly": "⚡ **Kattavuusanomalia (Daavid vastaan Goljat):**",
                "anomaly_text": "Kanava **{channel}** saavutti erinomaisen katselukertojen määrän ({views:,} katselukertaa, **{outlier}x** kanavan perustasoon nähden).\n",
                "sec_actionable": "💡 **Strateginen neuvonta ja sisältöaukot (Actionable Takeaway):**",
                "urgent": "• **Kiireellisesti tuotantoon:** Julkaise nopea reaktio tai vertailuvideo aiheesta «{title_short}...». Suositusikkuna: 48–72 tuntia.",
                "gap": "• **Sisältöaukko (Content Gap):** Yleisö kaipaa konkreettisia käyttötapauksia pelkän uutisoinnin sijaan.",
                "utility": "• **Hyötykoukku:** Rakenna «Top 5 käytännön ratkaisua» -video; hyötylistat tuottavat säännöllisesti yli 3-kertaisen tuloksen.",
                "empty": "Seuranta aktiivinen setille «{set_name}» ({count} kanavaa). Lisää kanavia tai käynnistä synkronointi."
            },
            "ka": {
                "title": f"📢 **YouTube Analytics ყოველდღიური დაიჯესტი ({current_date})**\n",
                "sec_overview": "📊 **ნიშის მიმოხილვა და დინამიკა:**",
                "overview_text": "ნიშაში «{set_name}» ლიდერობს არხი **{top_channel}**, რომელმაც აჩვენა მაღალი ჩართულობა და **{vph} VPH** სიჩქარე ახალ თემებზე.\n",
                "sec_breakthrough": "🔥 **დღის მთავარი გარღვევა:**",
                "breakthrough_sub": "«{title}» — {channel}\n📈 **{views:,}** ნახვა (Outlier: **{outlier}x**, VPH: **{vph}**).\nსიახლის ეფექტმა და ზუსტმა შეფუთვამ უზრუნველყო ვიდეოს წარმატება.\n",
                "sec_anomaly": "⚡ **წვდომის ანომალია (დავითი გოლიათის წინააღმდეგ):**",
                "anomaly_text": "არხმა **{channel}** აჩვენა შთამბეჭდავი შედეგი ({views:,} ნახვა, **{outlier}x** ნორმაზე მეტი).\n",
                "sec_actionable": "💡 **სტრატეგიული რჩევა და კონტენტის ხარვეზები (Actionable Takeaway):**",
                "urgent": "• **სასწრაფოდ წარმოებაში:** გამოუშვით სწრაფი რეაქცია ან ტესტი თემაზე «{title_short}...». აქტუალურობის ფანჯარა: 48–72 საათი.",
                "gap": "• **კონტენტის ხარვეზი (Content Gap):** მაყურებელი ეძებს პრაქტიკულ გამოყენებას და არა მხოლოდ სიახლეებს.",
                "utility": "• **სასარგებლო ჰუკი:** მოამზადეთ «ტოპ-5 პრაქტიკული გადაწყვეტა», რაც სტაბილურად აჩვენებს მაღალ კონვერსიას.",
                "empty": "მონიტორინგი აქტიურია «{set_name}»-სთვის ({count} არხი)."
            }
        }

        t = template_map.get(lang) or template_map["en"]
        lines = [t["title"], t["sec_overview"]]

        if top_videos:
            best = top_videos[0]
            top_channel = best.get("channel_title", "Leader")
            vph = int(best.get("velocity_vph", 0))
            outlier = best.get("outlier_score", 1.0)
            views = best.get("view_count", 0)
            title = best.get("title", "")
            title_short = title[:45]

            lines.append(t["overview_text"].format(set_name=set_name, top_channel=top_channel, vph=vph))
            lines.append(t["sec_breakthrough"])
            lines.append(t["breakthrough_sub"].format(title=title, channel=top_channel, views=views, outlier=outlier, vph=vph))

            # If an anomaly exists among other top videos, add anomaly section
            anomaly_video = next((v for v in top_videos[1:5] if v.get("outlier_score", 1.0) >= 1.8), None)
            if anomaly_video:
                lines.append(t["sec_anomaly"])
                lines.append(t["anomaly_text"].format(
                    channel=anomaly_video.get("channel_title", ""),
                    views=anomaly_video.get("view_count", 0),
                    outlier=anomaly_video.get("outlier_score", 1.0)
                ))

            lines.append(t["sec_actionable"])
            lines.append(t["urgent"].format(title_short=title_short))
            lines.append(t["gap"])
            lines.append(t["utility"])
        else:
            lines.append(t["empty"].format(set_name=set_name, count=len(channels_summary)))

        return "\n".join(lines)
