import logging
from typing import Any, Dict, List, Optional
import httpx
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.core.security import decrypt_secret
from backend.models.user import User
from backend.models.channel_set import ChannelSet
from backend.models.channel import Channel
from backend.services.analytics_service import AnalyticsService
from backend.services.gemini_service import GeminiService
from backend.services.log_service import LogService
from config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

TG_MESSAGES: Dict[str, Dict[str, str]] = {
    "account_linked": {
        "ru": "🎉 **Аккаунт успешно привязан!**\n\nДобро пожаловать, **{email}**!\nТеперь вам будут приходить персональные дайджесты по вашим наборам каналов с платформы [{dash_url}]({dash_url}).\n\nИспользуйте команду /help для списка возможностей.",
        "en": "🎉 **Account successfully linked!**\n\nWelcome, **{email}**!\nYou will now receive scheduled AI digests for your channel sets from [{dash_url}]({dash_url}).\n\nSend /help to explore available commands.",
        "de": "🎉 **Konto erfolgreich verknüpft!**\n\nWillkommen, **{email}**!\nSie erhalten nun geplante KI-Digests für Ihre Kanal-Sets von [{dash_url}]({dash_url}).\n\nSenden Sie /help für verfügbare Befehle.",
        "fi": "🎉 **Tili yhdistetty onnistuneesti!**\n\nTervetuloa, **{email}**!\nSaat nyt ajastetut tekoäly-yhteenvedot kanavaseteistäsi palvelusta [{dash_url}]({dash_url}).\n\nKirjoita /help nähdäksesi käytettävissä olevat komennot.",
        "ka": "🎉 **ანგარიში წარმატებით დაუკავშირდა!**\n\nმოგესალმებით, **{email}**!\nახლა მიიღებთ პერსონალურ დაიჯესტებს თქვენი არხების ნაკრებებზე პლატფორმიდან [{dash_url}]({dash_url}).\n\nგამოიყენეთ /help შესაძლებლობების სანახავად."
    },
    "invalid_code": {
        "ru": "⚠️ Код привязки устарел или недействителен.\n\nПожалуйста, нажмите кнопку **«Привязать Telegram»** заново в личном кабинете на [{dash_url}]({dash_url}) и перейдите по новой ссылке.",
        "en": "⚠️ The binding code is expired or invalid.\n\nPlease click **'Link Telegram Account'** again in your profile at [{dash_url}]({dash_url}) and use the new link.",
        "de": "⚠️ Der Verknüpfungscode ist abgelaufen oder ungültig.\n\nBitte klicken Sie auf [{dash_url}]({dash_url}) erneut auf **'Telegram verknüpfen'**.",
        "fi": "⚠️ Yhdistämiskoodi on vanhentunut tai virheellinen.\n\nNapsauta **'Yhdistä Telegram'** uudelleen osoitteessa [{dash_url}]({dash_url}).",
        "ka": "⚠️ დაკავშირების კოდი ვადაგასულია ან არასწორია.\n\nგთხოვთ დააჭიროთ **'Telegram-ის დაკავშირებას'** პროფილში [{dash_url}]({dash_url})-ზე."
    },
    "unlinked_start": {
        "ru": "👋 Привет! Чтобы связать этого бота с вашим аккаунтом на платформе аналитики:\n1. Зайдите в профиль на **{dash_url}**\n2. Нажмите кнопку **«Привязать Telegram»**\n3. Перейдите по ссылке или отправьте полученный 16-значный код прямо сюда в чат.",
        "en": "👋 Hello! To link this bot with your analytics platform account:\n1. Open your profile at **{dash_url}**\n2. Click **'Link Telegram Account'**\n3. Follow the link or send the 16-character binding code directly here in the chat.",
        "de": "👋 Hallo! Um diesen Bot mit Ihrem Konto auf der Analyseplattform zu verknüpfen:\n1. Öffnen Sie Ihr Profil auf **{dash_url}**\n2. Klicken Sie auf **'Telegram verknüpfen'**\n3. Folgen Sie dem Link oder senden Sie den 16-stelligen Code direkt hier in den Chat.",
        "fi": "👋 Hei! Yhdistääksesi tämän botin analytiikka-alustaan:\n1. Avaa profiilisi osoitteessa **{dash_url}**\n2. Napsauta **'Yhdistä Telegram'**\n3. Seuraa linkkiä tai lähetä 16-merkkinen koodi suoraan tähän chattiin.",
        "ka": "👋 გამარჯობა! ამ ბოტის თქვენს ანგარიშთან დასაკავშირებლად:\n1. შედით თქვენს პროფილში **{dash_url}**-ზე\n2. დააჭირეთ **'Telegram-ის დაკავშირებას'**\n3. გადადით ბმულზე ან გამოგზავნეთ 16-ნიშნა კოდი პირდაპირ აქ ჩატში."
    },
    "unlinked_msg": {
        "ru": "🔒 Ваш Telegram-аккаунт еще не привязан к личному кабинету.\nАвторизуйтесь на **{dash_url}**, нажмите «Привязать Telegram» в настройках профиля и отправьте сюда 16-значный код привязки.",
        "en": "🔒 Your Telegram account is not linked to your profile yet.\nSign in at **{dash_url}**, click 'Link Telegram Account' in Profile, and send the 16-character code here.",
        "de": "🔒 Ihr Telegram-Konto ist noch nicht verknüpft.\nMelden Sie sich auf **{dash_url}** an, klicken Sie im Profil auf 'Telegram verknüpfen' und senden Sie den 16-stelligen Code hierher.",
        "fi": "🔒 Telegram-tiliäsi ei ole vielä yhdistetty.\nKirjaudu osoitteeseen **{dash_url}**, napsauta profiilissa 'Yhdistä Telegram' ja lähetä 16-merkkinen koodi tänne.",
        "ka": "🔒 თქვენი Telegram ანგარიში ჯერ არ არის დაკავშირებული.\nშედით **{dash_url}**-ზე, დააჭირეთ 'Telegram-ის დაკავშირებას' პროფილში და გამოგზავნეთ 16-ნიშნა კოდი აქ."
    },
    "welcome_back": {
        "ru": "👋 С возвращением, **{email}**! Используйте /sets для выбора набора или /top для просмотра лидеров.",
        "en": "👋 Welcome back, **{email}**! Use /sets to select a channel set or /top to view top videos.",
        "de": "👋 Willkommen zurück, **{email}**! Nutzen Sie /sets zur Auswahl eines Sets oder /top für Top-Videos.",
        "fi": "👋 Tervetuloa takaisin, **{email}**! Käytä komentoa /sets valitaksesi setin tai /top nähdäksesi kärjen.",
        "ka": "👋 მოგესალმებით, **{email}**! გამოიყენეთ /sets ნაკრების ასარჩევად ან /top ტოპ ვიდეოებისთვის."
    },
    "help": {
        "ru": "🤖 **Доступные команды:**\n• /digest — Свежий исполнительный AI-дайджест ниши\n• /top — Топ-10 роликов текущего набора с виральными бейджами\n• /explain <номер_в_топе> — Глубокий разбор факторов успеха видео через Gemini\n• /sets — Просмотр и выбор активного набора каналов\n• /lang <ru|en|de|fi|ka> — Смена языка аналитики\n• /status — Проверка статуса API-ключей и расписания\n\n🌐 Личный кабинет: [{dash_url}]({dash_url})",
        "en": "🤖 **Available commands:**\n• /digest — Generate executive niche AI digest\n• /top — Top 10 videos of active set with viral badges\n• /explain <top_number> — Deep Gemini breakdown of video success factors\n• /sets — View and choose active channel set\n• /lang <ru|en|de|fi|ka> — Change language preference\n• /status — Check status of personal API keys and schedule\n\n🌐 Dashboard: [{dash_url}]({dash_url})",
        "de": "🤖 **Verfügbare Befehle:**\n• /digest — Aktuellen Executive-KI-Digest generieren\n• /top — Top 10 Videos des aktiven Sets mit Viral-Badges\n• /explain <nummer> — Tiefgehende Gemini-Erfolgsanalyse\n• /sets — Kanal-Sets anzeigen und auswählen\n• /lang <ru|en|de|fi|ka> — Sprache ändern\n• /status — Status der API-Schlüssel und des Zeitplans prüfen\n\n🌐 Dashboard: [{dash_url}]({dash_url})",
        "fi": "🤖 **Käytettävissä olevat komennot:**\n• /digest — Luo tuore johdon tekoäly-yhteenveto\n• /top — Aktiivisen setin top 10 videota viraalimerkeillä\n• /explain <numero> — Syvällinen Gemini-analyysi videon menestyksestä\n• /sets — Tarkastele ja valitse kanavasetti\n• /lang <ru|en|de|fi|ka> — Vaihda kieltä\n• /status — Tarkista API-avaimet ja aikataulu\n\n🌐 Hallintapaneeli: [{dash_url}]({dash_url})",
        "ka": "🤖 **ხელმისაწვდომი ბრძანებები:**\n• /digest — ნიშის AI დაიჯესტის გენერირება\n• /top — აქტიური ნაკრების ტოპ 10 ვიდეო ვირუსული ნიშნებით\n• /explain <ნომერი> — ვიდეოს წარმატების Gemini ანალიზი\n• /sets — არხების ნაკრებების ნახვა და არჩევა\n• /lang <ru|en|de|fi|ka> — ენის შეცვლა\n• /status — API გასაღებების და განრიგის სტატუსი\n\n🌐 პლატფორმა: [{dash_url}]({dash_url})"
    },
    "no_active_sets": {
        "ru": "❌ У вас нет активных наборов каналов. Создайте набор на {dash_url}.",
        "en": "❌ You have no active channel sets. Create a set at {dash_url}.",
        "de": "❌ Sie haben keine aktiven Kanal-Sets. Erstellen Sie eines auf {dash_url}.",
        "fi": "❌ Sinulla ei ole aktiivisia kanavasettejä. Luo setti osoitteessa {dash_url}.",
        "ka": "❌ თქვენ არ გაქვთ აქტიური არხების ნაკრები. შექმენით ნაკრები {dash_url}-ზე."
    },
    "digest_generating": {
        "ru": "⏳ Составляю executive AI-дайджест по набору «{name}»...",
        "en": "⏳ Generating executive AI digest for '{name}'...",
        "de": "⏳ Erstelle Executive-KI-Digest für «{name}»...",
        "fi": "⏳ Luodaan johdon tekoäly-yhteenvetoa setille «{name}»...",
        "ka": "⏳ იქმნება AI დაიჯესტი ნაკრებისთვის «{name}»..."
    },
    "no_sets": {
        "ru": "У вас пока нет созданных наборов каналов. Создайте первый набор в дашборде на {dash_url}.",
        "en": "You don't have any channel sets yet. Create your first set in the dashboard at {dash_url}.",
        "de": "Sie haben noch keine Kanal-Sets. Erstellen Sie Ihr erstes Set auf {dash_url}.",
        "fi": "Sinulla ei ole vielä kanavasettejä. Luo ensimmäinen setti osoitteessa {dash_url}.",
        "ka": "თქვენ ჯერ არ გაქვთ შექმნილი არხების ნაკრები. შექმენით პირველი ნაკრები {dash_url}-ზე."
    },
    "sets_title": {
        "ru": "📁 **Ваши наборы каналов:**",
        "en": "📁 **Your Channel Sets:**",
        "de": "📁 **Ihre Kanal-Sets:**",
        "fi": "📁 **Kanavasetit:**",
        "ka": "📁 **თქვენი არხების ნაკრებები:**"
    },
    "sets_active": {
        "ru": " 🟢 (Активен)",
        "en": " 🟢 (Active)",
        "de": " 🟢 (Aktiv)",
        "fi": " 🟢 (Aktiivinen)",
        "ka": " 🟢 (აქტიური)"
    },
    "sets_instruction": {
        "ru": "\nЧтобы выбрать набор, отправьте команду: `/set <номер>` (например: `/set 1`)",
        "en": "\nTo select a set, send: `/set <number>` (e.g. `/set 1`)",
        "de": "\nUm ein Set auszuwählen, senden Sie: `/set <nummer>` (z.B. `/set 1`)",
        "fi": "\nValitaksesi setin lähetä komento: `/set <numero>` (esim. `/set 1`)",
        "ka": "\nნაკრების ასარჩევად გაგზავნეთ: `/set <ნომერი>` (მაგ: `/set 1`)"
    },
    "set_switched": {
        "ru": "✅ Активным выбран набор: **«{name}»**! Теперь команды /top и дайджесты работают по нему.",
        "en": "✅ Active set switched to: **'{name}'**! Commands like /top and digests will now use this set.",
        "de": "✅ Aktives Set geändert auf: **«{name}»**! Nun basieren /top und Digests auf diesem Set.",
        "fi": "✅ Aktiiviseksi valittu: **«{name}»**! /top ja yhteenvedot käyttävät nyt tätä settiä.",
        "ka": "✅ აქტიურ ნაკრებად არჩეულია: **«{name}»**! /top და დაიჯესტები იმუშავებს ამ ნაკრებზე."
    },
    "set_not_found": {
        "ru": "❌ Набор не найден. Используйте /sets для просмотра номеров наборов.",
        "en": "❌ Channel set not found. Use /sets to see available numbers.",
        "de": "❌ Set nicht gefunden. Nutzen Sie /sets, um Nummern anzuzeigen.",
        "fi": "❌ Settiä ei löytynyt. Käytä komentoa /sets nähdäksesi numerot.",
        "ka": "❌ ნაკრები ვერ მოიძებნა. გამოიყენეთ /sets ნომრების სანახავად."
    },
    "lang_updated": {
        "ru": "🌐 Язык интерфейса и отчетов успешно изменен на: **{lang}**!",
        "en": "🌐 Interface and report language successfully updated to: **{lang}**!",
        "de": "🌐 Sprache für Benutzeroberfläche und Berichte aktualisiert auf: **{lang}**!",
        "fi": "🌐 Käyttöliittymän ja raporttien kieli vaihdettu: **{lang}**!",
        "ka": "🌐 ინტერფეისის და რეპორტების ენა წარმატებით შეიცვალა: **{lang}**!"
    },
    "lang_help": {
        "ru": "Укажите язык: `/lang ru`, `/lang en`, `/lang de`, `/lang fi` или `/lang ka`.",
        "en": "Specify language: `/lang ru`, `/lang en`, `/lang de`, `/lang fi` or `/lang ka`.",
        "de": "Sprache angeben: `/lang ru`, `/lang en`, `/lang de`, `/lang fi` oder `/lang ka`.",
        "fi": "Määritä kieli: `/lang ru`, `/lang en`, `/lang de`, `/lang fi` tai `/lang ka`.",
        "ka": "მიუთითეთ ენა: `/lang ru`, `/lang en`, `/lang de`, `/lang fi` ან `/lang ka`."
    },
    "top_no_videos": {
        "ru": "В наборе «{name}» пока нет собранных роликов. Добавьте каналы на {dash_url} или запустите синхронизацию.",
        "en": "No videos collected in '{name}' yet. Add channels at {dash_url} or trigger sync.",
        "de": "Noch keine Videos im Set «{name}». Fügen Sie Kanäle auf {dash_url} hinzu oder synchronisieren Sie.",
        "fi": "Setissä «{name}» ei ole vielä videoita. Lisää kanavia osoitteessa {dash_url} tai synkronoi.",
        "ka": "ნაკრებში «{name}» ჯერ არ არის ვიდეოები. დაამატეთ არხები {dash_url}-ზე ან დაიწყეთ სინქრონიზაცია."
    },
    "top_title": {
        "ru": "🏆 **Топ видео набора «{name}»:**\n",
        "en": "🏆 **Top Videos for '{name}':**\n",
        "de": "🏆 **Top-Videos im Set «{name}»:**\n",
        "fi": "🏆 **Top-videot setissä «{name}»:**\n",
        "ka": "🏆 **ტოპ ვიდეოები ნაკრებში «{name}»:**\n"
    },
    "top_channel": {
        "ru": "Канал",
        "en": "Channel",
        "de": "Kanal",
        "fi": "Kanava",
        "ka": "არხი"
    },
    "top_explain_hint": {
        "ru": "Для глубокого AI-разбора ролика отправьте: `/explain <номер>` (например: `/explain 1`)",
        "en": "For deep AI analysis of a video, send: `/explain <number>` (e.g. `/explain 1`)",
        "de": "Für eine detaillierte KI-Analyse senden Sie: `/explain <nummer>` (z.B. `/explain 1`)",
        "fi": "Syvällistä tekoälyanalyysiä varten lähetä: `/explain <numero>` (esim. `/explain 1`)",
        "ka": "ვიდეოს AI ანალიზისთვის გაგზავნეთ: `/explain <ნომერი>` (მაგ: `/explain 1`)"
    },
    "explain_need_number": {
        "ru": "Укажите номер видео из топа. Например: `/explain 1`.",
        "en": "Please specify the video number from /top. E.g.: `/explain 1`.",
        "de": "Bitte geben Sie die Video-Nummer aus /top an. Z.B.: `/explain 1`.",
        "fi": "Määritä videon numero listalta /top. Esim.: `/explain 1`.",
        "ka": "მიუთითეთ ვიდეოს ნომერი /top-იდან. მაგ: `/explain 1`."
    },
    "explain_choose_set": {
        "ru": "Выберите активный набор через /sets.",
        "en": "Choose an active set first via /sets.",
        "de": "Wählen Sie zuerst ein aktives Set über /sets.",
        "fi": "Valitse ensin aktiivinen setti komennolla /sets.",
        "ka": "ჯერ აირჩიეთ აქტიური ნაკრები /sets-ით."
    },
    "explain_not_found": {
        "ru": "❌ Видео не найдено в текущем топе. Сначала вызовите /top.",
        "en": "❌ Video not found in the current top list. Call /top first.",
        "de": "❌ Video nicht in den aktuellen Top-Videos gefunden. Rufen Sie zuerst /top auf.",
        "fi": "❌ Videota ei löytynyt nykyiseltä listalta. Kutsu ensin /top.",
        "ka": "❌ ვიდეო ვერ მოიძებნა მიმდინარე სიაში. ჯერ გამოიძახეთ /top."
    },
    "explain_header": {
        "ru": "🧠 **AI-Разбор успеха ролика (Gemini):**",
        "en": "🧠 **AI Video Success Breakdown (Gemini):**",
        "de": "🧠 **KI-Erfolgsanalyse des Videos (Gemini):**",
        "fi": "🧠 **Videon menestysanalyysi (Gemini):**",
        "ka": "🧠 **ვიდეოს წარმატების AI ანალიზი (Gemini):**"
    },
    "explain_metrics_label": {
        "ru": "📊 **Метрики:** {views:,} просм. | {outlier}x от нормы | {velocity} VPH",
        "en": "📊 **Metrics:** {views:,} views | {outlier}x baseline | {velocity} VPH",
        "de": "📊 **Metriken:** {views:,} Aufrufe | {outlier}x Norm | {velocity} VPH",
        "fi": "📊 **Mittarit:** {views:,} katselukertaa | {outlier}x perustaso | {velocity} VPH",
        "ka": "📊 **მეტრები:** {views:,} ნახვა | {outlier}x ნორმაზე | {velocity} VPH"
    },
    "explain_verdict": {
        "ru": "🎯 **Вердикт:**",
        "en": "🎯 **Verdict:**",
        "de": "🎯 **Urteil:**",
        "fi": "🎯 **Tuomio:**",
        "ka": "🎯 **ვერდიქტი:**"
    },
    "explain_hook": {
        "ru": "🎣 **Хук и заголовок:**",
        "en": "🎣 **Hook & Packaging:**",
        "de": "🎣 **Hook & Verpackung:**",
        "fi": "🎣 **Koukku ja otsikko:**",
        "ka": "🎣 **ჰუკი და შეფუთვა:**"
    },
    "explain_trend": {
        "ru": "🔥 **Оседланный тренд:**",
        "en": "🔥 **Trend Alignment:**",
        "de": "🔥 **Trend-Ausrichtung:**",
        "fi": "🔥 **Trendin hyödyntäminen:**",
        "ka": "🔥 **ტრენდის ათვისება:**"
    },
    "explain_takeaway": {
        "ru": "💡 **Рекомендация автору:**",
        "en": "💡 **Creator Takeaway:**",
        "de": "💡 **Handlungsempfehlung:**",
        "fi": "💡 **Suositus sisällöntuottajalle:**",
        "ka": "💡 **რეკომენდაცია ავტორს:**"
    },
    "status_header": {
        "ru": "⚙️ **Статус вашего аккаунта ({email}):**",
        "en": "⚙️ **Account Status ({email}):**",
        "de": "⚙️ **Kontostatus ({email}):**",
        "fi": "⚙️ **Tilin tila ({email}):**",
        "ka": "⚙️ **თქვენი ანგარიშის სტატუსი ({email}):**"
    },
    "status_configured": {
        "ru": "🟢 Настроен",
        "en": "🟢 Configured",
        "de": "🟢 Konfiguriert",
        "fi": "🟢 Määritetty",
        "ka": "🟢 კონფიგურირებულია"
    },
    "status_not_configured": {
        "ru": "🔴 Не настроен / Не валиден",
        "en": "🔴 Not configured / Invalid",
        "de": "🔴 Nicht konfiguriert / Ungültig",
        "fi": "🔴 Ei määritetty / Virheellinen",
        "ka": "🔴 არ არის კონფიგურირებული / არავალიდური"
    },
    "status_active_set_label": {
        "ru": "Активный набор",
        "en": "Active Set",
        "de": "Aktives Set",
        "fi": "Aktiivinen setti",
        "ka": "აქტიური ნაკრები"
    },
    "status_not_selected": {
        "ru": "Не выбран",
        "en": "Not selected",
        "de": "Nicht ausgewählt",
        "fi": "Ei valittu",
        "ka": "არ არის არჩეული"
    },
    "status_lang_label": {
        "ru": "Язык отчетов",
        "en": "Report Language",
        "de": "Berichtssprache",
        "fi": "Raportointikieli",
        "ka": "რეპორტის ენა"
    },
    "status_manage": {
        "ru": "Управление ключами и наборами: [{dash_url}]({dash_url})",
        "en": "Manage keys and channel sets: [{dash_url}]({dash_url})",
        "de": "Schlüssel und Sets verwalten: [{dash_url}]({dash_url})",
        "fi": "Hallinnoi avaimia ja kanavasettejä: [{dash_url}]({dash_url})",
        "ka": "გასაღებების და ნაკრებების მართვა: [{dash_url}]({dash_url})"
    },
    "unknown_cmd": {
        "ru": "Неизвестная команда. Отправьте /help для списка команд или /menu для вызова меню.",
        "en": "Unknown command. Send /help for the list of available commands or /menu for the control menu.",
        "de": "Unbekannter Befehl. Senden Sie /help für Befehle oder /menu für das Menü.",
        "fi": "Tuntematon komento. Lähetä /help tai /menu nähdäksesi valikon.",
        "ka": "უცნობი ბრძანება. გააგზავნეთ /help ან /menu მენიუსთვის."
    },
    "menu_header": {
        "ru": "📋 **Интерактивное меню YouTube Analytics:**\nВыберите действие кнопками ниже или используйте команды:",
        "en": "📋 **YouTube Analytics Interactive Menu:**\nSelect an action using the buttons below or use slash commands:",
        "de": "📋 **YouTube Analytics Interaktives Menü:**\nWählen Sie unten eine Aktion oder nutzen Sie Befehle:",
        "fi": "📋 **YouTube Analytics Interaktiivinen valikko:**\nValitse toiminto alta tai käytä komentoja:",
        "ka": "📋 **YouTube Analytics ინტერაქტიული მენიუ:**\nაირჩიეთ მოქმედება ქვემოთ ან გამოიყენეთ ბრძანებები:"
    },
    "choose_language": {
        "ru": "🌐 **Выберите желаемый язык аналитики:**",
        "en": "🌐 **Select your preferred analytics language:**",
        "de": "🌐 **Wählen Sie Ihre bevorzugte Analysesprache:**",
        "fi": "🌐 **Valitse haluamasi analytiikan kieli:**",
        "ka": "🌐 **აირჩიეთ ანალიტიკის სასურველი ენა:**"
    },
    "explain_prompt": {
        "ru": "🧠 **AI-Разбор виральности ролика:**\nЧтобы разобрать ролик из топа, отправьте команду с номером: `/explain <номер>`\nНапример: `/explain 1` (для разбора видео #1)",
        "en": "🧠 **AI Video Virality Breakdown:**\nTo break down a top video, send the command with its index: `/explain <number>`\nExample: `/explain 1` (to analyze video #1)",
        "de": "🧠 **KI-Videoerfolgsanalyse:**\nUm ein Video zu analysieren, senden Sie: `/explain <nummer>`\nBeispiel: `/explain 1`",
        "fi": "🧠 **Tekoälyn viraalianalyysi:**\nAnalysoidaksesi videon lähetä: `/explain <numero>`\nEsimerkki: `/explain 1`",
        "ka": "🧠 **ვიდეოს ვირუსულობის AI ანალიზი:**\nვიდეოს გასაანალიზებლად გაგზავნეთ: `/explain <ნომერი>`\nმაგალითად: `/explain 1`"
    }
}


class TelegramService:
    @staticmethod
    def _chunk_text(text: str, max_chars: int = 4000) -> List[str]:
        """Split text into chunks not exceeding max_chars, preserving paragraphs."""
        if not text or len(text) <= max_chars:
            return [text] if text else []

        chunks: List[str] = []
        current_chunk: List[str] = []
        current_len = 0

        for line in text.split("\n"):
            line_len = len(line) + 1
            if current_len + line_len > max_chars and current_chunk:
                chunks.append("\n".join(current_chunk))
                current_chunk = []
                current_len = 0

            if len(line) > max_chars:
                for i in range(0, len(line), max_chars):
                    sub = line[i:i + max_chars]
                    if i + max_chars < len(line):
                        chunks.append(sub)
                    else:
                        current_chunk.append(sub)
                        current_len += len(sub)
            else:
                current_chunk.append(line)
                current_len += line_len

        if current_chunk:
            chunks.append("\n".join(current_chunk))

        return chunks

    @classmethod
    def _t(cls, key: str, lang: str = "en", **kwargs: Any) -> str:
        """Translate a message key into target language with string interpolation."""
        translations = TG_MESSAGES.get(key, {})
        text_tpl = translations.get(lang) or translations.get("en") or translations.get("ru") or key
        try:
            return text_tpl.format(**kwargs)
        except Exception:
            return text_tpl

    @staticmethod
    def get_main_reply_keyboard(lang: str = "en") -> Dict[str, Any]:
        """Generate persistent reply keyboard with command buttons in user language."""
        labels = {
            "ru": {
                "top": "📊 Топ-10 видео",
                "digest": "📢 AI-Дайджест",
                "sets": "📁 Наборы каналов",
                "explain": "🧠 AI-Разбор",
                "status": "⚙️ Статус ключей",
                "lang": "🌐 Сменить язык",
                "menu": "📋 Главное меню",
                "help": "❓ Помощь"
            },
            "en": {
                "top": "📊 Top 10 Videos",
                "digest": "📢 AI Digest",
                "sets": "📁 Channel Sets",
                "explain": "🧠 AI Breakdown",
                "status": "⚙️ Status & Keys",
                "lang": "🌐 Change Language",
                "menu": "📋 Main Menu",
                "help": "❓ Help"
            },
            "de": {
                "top": "📊 Top 10 Videos",
                "digest": "📢 KI-Digest",
                "sets": "📁 Kanal-Sets",
                "explain": "🧠 KI-Analyse",
                "status": "⚙️ Status",
                "lang": "🌐 Sprache",
                "menu": "📋 Hauptmenü",
                "help": "❓ Hilfe"
            },
            "fi": {
                "top": "📊 Top 10 Videot",
                "digest": "📢 Tekoäly-kooste",
                "sets": "📁 Kanavasetit",
                "explain": "🧠 Tekoäly-analyysi",
                "status": "⚙️ Tila",
                "lang": "🌐 Kieli",
                "menu": "📋 Päävalikko",
                "help": "❓ Ohje"
            },
            "ka": {
                "top": "📊 ტოპ 10 ვიდეო",
                "digest": "📢 AI დაიჯესტი",
                "sets": "📁 არხების ნაკრები",
                "explain": "🧠 AI ანალიზი",
                "status": "⚙️ სტატუსი",
                "lang": "🌐 ენის შეცვლა",
                "menu": "📋 მთავარი მენიუ",
                "help": "❓ დახმარება"
            }
        }
        l = labels.get(lang, labels["en"])
        return {
            "keyboard": [
                [{"text": l["top"]}, {"text": l["digest"]}],
                [{"text": l["sets"]}, {"text": l["explain"]}],
                [{"text": l["status"]}, {"text": l["lang"]}],
                [{"text": l["menu"]}, {"text": l["help"]}]
            ],
            "resize_keyboard": True,
            "is_persistent": True
        }

    @staticmethod
    def get_inline_menu(lang: str = "en", dash_url: str = "") -> Dict[str, Any]:
        """Generate interactive inline menu with callback buttons."""
        titles = {
            "ru": {
                "top": "📊 Топ-10 видео",
                "digest": "📢 Сгенерировать AI-дайджест",
                "sets": "📁 Наборы каналов",
                "explain": "🧠 Разбор виральности",
                "status": "⚙️ Статус и ключи",
                "lang": "🌐 Выбрать язык",
                "web": "💻 Открыть Web Dashboard",
                "help": "❓ Справка"
            },
            "en": {
                "top": "📊 Top 10 Videos",
                "digest": "📢 Generate AI Digest",
                "sets": "📁 Channel Sets",
                "explain": "🧠 Virality Breakdown",
                "status": "⚙️ Status & Keys",
                "lang": "🌐 Choose Language",
                "web": "💻 Open Web Dashboard",
                "help": "❓ Help"
            },
            "de": {
                "top": "📊 Top 10 Videos",
                "digest": "📢 KI-Digest generieren",
                "sets": "📁 Kanal-Sets",
                "explain": "🧠 Erfolgsanalyse",
                "status": "⚙️ Status & Schlüssel",
                "lang": "🌐 Sprache wählen",
                "web": "💻 Web-Dashboard öffnen",
                "help": "❓ Hilfe"
            },
            "fi": {
                "top": "📊 Top 10 Videot",
                "digest": "📢 Luo tekoäly-kooste",
                "sets": "📁 Kanavasetit",
                "explain": "🧠 Viraalianalyysi",
                "status": "⚙️ Tila ja avaimet",
                "lang": "🌐 Valitse kieli",
                "web": "💻 Avaa Web Dashboard",
                "help": "❓ Ohje"
            },
            "ka": {
                "top": "📊 ტოპ 10 ვიდეო",
                "digest": "📢 AI დაიჯესტის გენერირება",
                "sets": "📁 არხების ნაკრებები",
                "explain": "🧠 ვირუსულობის ანალიზი",
                "status": "⚙️ სტატუსი და გასაღებები",
                "lang": "🌐 ენის არჩევა",
                "web": "💻 Web პლატფორმის გახსნა",
                "help": "❓ დახმარება"
            }
        }
        t = titles.get(lang, titles["en"])
        kb = [
            [{"text": t["digest"], "callback_data": "menu:digest"}],
            [{"text": t["top"], "callback_data": "menu:top"}, {"text": t["explain"], "callback_data": "menu:explain"}],
            [{"text": t["sets"], "callback_data": "menu:sets"}, {"text": t["status"], "callback_data": "menu:status"}],
            [{"text": t["lang"], "callback_data": "menu:lang"}, {"text": t["help"], "callback_data": "menu:help"}]
        ]
        if dash_url:
            kb.append([{"text": t["web"], "url": dash_url}])
        return {"inline_keyboard": kb}

    @staticmethod
    def get_language_inline_keyboard() -> Dict[str, Any]:
        """Generate inline keyboard for language switching."""
        return {
            "inline_keyboard": [
                [
                    {"text": "🇷🇺 Русский", "callback_data": "lang:ru"},
                    {"text": "🇬🇧 English", "callback_data": "lang:en"}
                ],
                [
                    {"text": "🇩🇪 Deutsch", "callback_data": "lang:de"},
                    {"text": "🇫🇮 Suomi", "callback_data": "lang:fi"}
                ],
                [
                    {"text": "🇬🇪 ქართული", "callback_data": "lang:ka"}
                ],
                [
                    {"text": "🔙 Назад / Back", "callback_data": "menu:back"}
                ]
            ]
        }

    @classmethod
    def answer_callback_query(cls, callback_query_id: str, text: Optional[str] = None) -> bool:
        """Acknowledge Telegram callback query to dismiss loading state."""
        bot_token = settings.TELEGRAM_BOT_TOKEN
        if not bot_token:
            return False
        try:
            with httpx.Client(timeout=5.0) as client:
                payload: Dict[str, Any] = {"callback_query_id": callback_query_id}
                if text:
                    payload["text"] = text
                client.post(f"https://api.telegram.org/bot{bot_token}/answerCallbackQuery", json=payload)
                return True
        except Exception:
            return False

    @classmethod
    def send_message(
        cls,
        chat_id: int | str,
        text: str,
        parse_mode: str = "Markdown",
        reply_markup: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Send message to Telegram with auto-splitting for long messages, reply_markup support, and plain-text fallback."""
        bot_token = settings.TELEGRAM_BOT_TOKEN
        if not bot_token or " " in bot_token:
            logger.info(f"[MOCK TG SEND] to {chat_id}: {text[:100]}...")
            return True

        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        chunks = cls._chunk_text(text, max_chars=4000)
        overall_success = True

        try:
            with httpx.Client(timeout=15.0) as client:
                for idx, chunk in enumerate(chunks):
                    payload: Dict[str, Any] = {"chat_id": chat_id, "text": chunk}
                    if parse_mode:
                        payload["parse_mode"] = parse_mode
                    if idx == len(chunks) - 1 and reply_markup:
                        payload["reply_markup"] = reply_markup

                    res = client.post(url, json=payload)
                    if res.status_code != 200 and parse_mode:
                        payload.pop("parse_mode", None)
                        res = client.post(url, json=payload)
                    if res.status_code != 200:
                        overall_success = False
                        logger.error(f"Telegram error delivering chunk to {chat_id}: {res.text}")
                return overall_success
        except Exception as e:
            logger.error(f"Network error sending telegram message: {e}")
            return False

    @classmethod
    def get_bot_info(cls) -> Optional[Dict[str, Any]]:
        """Fetch bot metadata from Telegram getMe."""
        bot_token = settings.TELEGRAM_BOT_TOKEN
        if not bot_token or " " in bot_token:
            return None
        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.get(f"https://api.telegram.org/bot{bot_token}/getMe")
                if res.status_code == 200 and res.json().get("ok"):
                    return res.json().get("result")
                logger.warning(f"Telegram getMe failed ({res.status_code}): {res.text}")
        except Exception as e:
            logger.error(f"Error fetching Telegram getMe: {e}")
        return None

    @classmethod
    def get_webhook_info(cls) -> Optional[Dict[str, Any]]:
        """Fetch current webhook registration status from Telegram getWebhookInfo."""
        bot_token = settings.TELEGRAM_BOT_TOKEN
        if not bot_token or " " in bot_token:
            return None
        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.get(f"https://api.telegram.org/bot{bot_token}/getWebhookInfo")
                if res.status_code == 200 and res.json().get("ok"):
                    return res.json().get("result")
                logger.warning(f"Telegram getWebhookInfo failed ({res.status_code}): {res.text}")
        except Exception as e:
            logger.error(f"Error fetching Telegram getWebhookInfo: {e}")
        return None

    @classmethod
    def register_webhook(cls) -> Dict[str, Any]:
        """Automatically register webhook URL and bot commands with Telegram."""
        bot_token = settings.TELEGRAM_BOT_TOKEN
        if not bot_token or " " in bot_token:
            return {"ok": False, "description": "TELEGRAM_BOT_TOKEN is not configured"}

        webhook_url = f"https://{settings.DOKPLOY_API_DOMAIN}/api/v1/telegram/webhook"
        tg_url = f"https://api.telegram.org/bot{bot_token}/setWebhook"
        params: Dict[str, Any] = {
            "url": webhook_url,
            "drop_pending_updates": False
        }
        wh_secret = (settings.TELEGRAM_WEBHOOK_SECRET or "").strip().strip('"').strip("'")
        if wh_secret:
            params["secret_token"] = wh_secret

        result = {"ok": False}
        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.post(tg_url, json=params)
                result = res.json()
                logger.info(f"Telegram setWebhook result: {result}")

                # Register bot commands menu (multilingual)
                commands_en = [
                    {"command": "menu", "description": "Interactive command menu"},
                    {"command": "digest", "description": "Latest executive niche AI digest"},
                    {"command": "top", "description": "Top 10 videos of active set"},
                    {"command": "explain", "description": "AI video success breakdown"},
                    {"command": "sets", "description": "Channel sets & switch active"},
                    {"command": "status", "description": "Check API keys & schedule"},
                    {"command": "lang", "description": "Change language (ru, en, de, fi, ka)"},
                    {"command": "help", "description": "Commands help"}
                ]
                commands_ru = [
                    {"command": "menu", "description": "Главное меню с кнопками"},
                    {"command": "digest", "description": "Свежий AI-дайджест ниши"},
                    {"command": "top", "description": "Топ-10 видео активного набора"},
                    {"command": "explain", "description": "AI-разбор успеха ролика"},
                    {"command": "sets", "description": "Наборы каналов и переключение"},
                    {"command": "status", "description": "Статус API-ключей и расписания"},
                    {"command": "lang", "description": "Смена языка (ru, en, de, fi, ka)"},
                    {"command": "help", "description": "Справка по командам"}
                ]
                commands_de = [
                    {"command": "menu", "description": "Interaktives Befehlsmenü"},
                    {"command": "digest", "description": "Aktuellen Executive-KI-Digest generieren"},
                    {"command": "top", "description": "Top 10 Videos des aktiven Sets"},
                    {"command": "explain", "description": "Tiefgehende Gemini-Erfolgsanalyse"},
                    {"command": "sets", "description": "Kanal-Sets anzeigen und auswählen"},
                    {"command": "status", "description": "Status der API-Schlüssel prüfen"},
                    {"command": "lang", "description": "Sprache ändern"},
                    {"command": "help", "description": "Befehlshilfe"}
                ]
                commands_fi = [
                    {"command": "menu", "description": "Interaktiivinen komentovalikko"},
                    {"command": "digest", "description": "Luo tuore johdon tekoäly-yhteenveto"},
                    {"command": "top", "description": "Aktiivisen setin top 10 videota"},
                    {"command": "explain", "description": "Syvällinen Gemini-analyysi videosta"},
                    {"command": "sets", "description": "Tarkastele ja valitse kanavasetti"},
                    {"command": "status", "description": "Tarkista API-avaimet ja aikataulu"},
                    {"command": "lang", "description": "Vaihda kieltä"},
                    {"command": "help", "description": "Komentojen ohje"}
                ]
                commands_ka = [
                    {"command": "menu", "description": "ინტერაქტიული მენიუ"},
                    {"command": "digest", "description": "ნიშის AI დაიჯესტის გენერირება"},
                    {"command": "top", "description": "აქტიური ნაკრების ტოპ 10 ვიდეო"},
                    {"command": "explain", "description": "ვიდეოს წარმატების Gemini ანალიზი"},
                    {"command": "sets", "description": "არხების ნაკრებების ნახვა და არჩევა"},
                    {"command": "status", "description": "API გასაღებების სტატუსი"},
                    {"command": "lang", "description": "ენის შეცვლა"},
                    {"command": "help", "description": "დახმარება"}
                ]
                client.post(f"https://api.telegram.org/bot{bot_token}/setMyCommands", json={"commands": commands_en})
                client.post(f"https://api.telegram.org/bot{bot_token}/setMyCommands", json={"commands": commands_ru, "language_code": "ru"})
                client.post(f"https://api.telegram.org/bot{bot_token}/setMyCommands", json={"commands": commands_de, "language_code": "de"})
                client.post(f"https://api.telegram.org/bot{bot_token}/setMyCommands", json={"commands": commands_fi, "language_code": "fi"})
                client.post(f"https://api.telegram.org/bot{bot_token}/setMyCommands", json={"commands": commands_ka, "language_code": "ka"})
                client.post(f"https://api.telegram.org/bot{bot_token}/setChatMenuButton", json={"menu_button": {"type": "commands"}})
        except Exception as e:
            logger.error(f"Error registering Telegram webhook: {e}")
            result = {"ok": False, "description": str(e)}

        return result

    @classmethod
    def _process_digest_command(cls, db: Session, user: User, chat_id: str, user_lang: str, dash_url: str) -> bool:
        """Execute /digest logic and deliver executive AI digest."""
        active_set_id = user.active_set_id
        if not active_set_id:
            first_set = db.query(ChannelSet).filter(ChannelSet.user_id == user.id).first()
            if first_set:
                user.active_set_id = first_set.id
                db.commit()
                active_set_id = first_set.id

        if not active_set_id:
            cls.send_message(chat_id, cls._t("no_active_sets", user_lang, dash_url=dash_url))
            return True

        active_set = db.query(ChannelSet).filter(ChannelSet.id == active_set_id).first()
        cls.send_message(chat_id, cls._t("digest_generating", user_lang, name=active_set.name))

        enriched_videos = AnalyticsService.get_set_enriched_videos(db, user.id, active_set_id, limit=15)
        channels = db.query(Channel).filter(Channel.user_id == user.id, Channel.set_id == active_set_id).all()
        channels_summary = [{"title": c.title, "subscriber_count": c.subscriber_count} for c in channels]

        anomalies = []
        for v in enriched_videos:
            if v.get("outlier_score", 1.0) >= 1.8:
                anomalies.append(f"Channel {v.get('channel_title')}: «{v.get('title')}» — {v.get('view_count', 0):,} views ({v.get('outlier_score')}x)")

        gemini_key = decrypt_secret(user.gemini_api_key_encrypted)
        digest_text = GeminiService.generate_daily_digest(
            set_name=active_set.name,
            channels_summary=channels_summary,
            top_videos=enriched_videos,
            anomalies=anomalies,
            target_language=user_lang,
            gemini_api_key=gemini_key,
            user_id=user.id,
            user_email=user.email,
            db=db
        )
        cls.send_message(chat_id, digest_text, reply_markup=cls.get_main_reply_keyboard(user_lang))
        return True

    @classmethod
    def _process_top_command(cls, db: Session, user: User, chat_id: str, user_lang: str, dash_url: str) -> bool:
        """Execute /top logic and deliver top 10 videos with viral badges."""
        active_set_id = user.active_set_id
        if not active_set_id:
            first_set = db.query(ChannelSet).filter(ChannelSet.user_id == user.id).first()
            if first_set:
                user.active_set_id = first_set.id
                db.commit()
                active_set_id = first_set.id

        if not active_set_id:
            cls.send_message(chat_id, cls._t("no_active_sets", user_lang, dash_url=dash_url))
            return True

        active_set = db.query(ChannelSet).filter(ChannelSet.id == active_set_id).first()
        videos = AnalyticsService.get_set_enriched_videos(db, user.id, active_set_id, limit=10)
        if not videos:
            cls.send_message(chat_id, cls._t("top_no_videos", user_lang, name=active_set.name, dash_url=dash_url))
            return True

        lines = [cls._t("top_title", user_lang, name=active_set.name)]
        channel_label = cls._t("top_channel", user_lang)
        for idx, v in enumerate(videos, 1):
            badges_str = " ".join(v.get("badges", []))
            lines.append(f"**#{idx}** {badges_str}\n• **«{v.get('title')}»**\n  {channel_label}: {v.get('channel_title')} | 👁 {v.get('view_count'):,} | VPH: {v.get('velocity_vph')}\n")
        lines.append(cls._t("top_explain_hint", user_lang))
        cls.send_message(chat_id, "\n".join(lines), reply_markup=cls.get_main_reply_keyboard(user_lang))
        return True

    @classmethod
    def _process_sets_command(cls, db: Session, user: User, chat_id: str, user_lang: str, dash_url: str) -> bool:
        """Execute /sets logic showing channel sets with interactive switch buttons."""
        sets = db.query(ChannelSet).filter(ChannelSet.user_id == user.id).all()
        if not sets:
            cls.send_message(chat_id, cls._t("no_sets", user_lang, dash_url=dash_url))
            return True
        lines = [cls._t("sets_title", user_lang)]
        inline_buttons = []
        for idx, s in enumerate(sets, 1):
            is_active = (s.id == user.active_set_id)
            active_mark = cls._t("sets_active", user_lang) if is_active else ""
            lines.append(f"{idx}. **{s.name}**{active_mark} — {s.schedule_time} ({s.schedule_timezone})")
            btn_text = f"✅ {s.name}" if is_active else f"📁 {s.name}"
            inline_buttons.append([{"text": btn_text, "callback_data": f"set:{s.id}"}])

        lines.append(cls._t("sets_instruction", user_lang))
        reply_markup = {"inline_keyboard": inline_buttons}
        cls.send_message(chat_id, "\n".join(lines), reply_markup=reply_markup)
        return True

    @classmethod
    def _process_status_command(cls, db: Session, user: User, chat_id: str, user_lang: str, dash_url: str) -> bool:
        """Execute /status logic reporting API keys, active set, and language."""
        yt_status = cls._t("status_configured", user_lang) if user.youtube_api_key_valid else cls._t("status_not_configured", user_lang)
        gemini_status = cls._t("status_configured", user_lang) if user.gemini_api_key_valid else cls._t("status_not_configured", user_lang)
        active_set = db.query(ChannelSet).filter(ChannelSet.id == user.active_set_id).first() if user.active_set_id else None
        set_name = active_set.name if active_set else cls._t("status_not_selected", user_lang)

        status_header = cls._t("status_header", user_lang, email=user.email)
        set_label = cls._t("status_active_set_label", user_lang)
        lang_label = cls._t("status_lang_label", user_lang)
        manage_link = cls._t("status_manage", user_lang, dash_url=dash_url)

        msg = (
            f"{status_header}\n\n"
            f"• YouTube API Key: {yt_status}\n"
            f"• Gemini API Key: {gemini_status}\n"
            f"• {set_label}: **{set_name}**\n"
            f"• {lang_label}: **{user_lang}**\n\n"
            f"{manage_link}"
        )
        cls.send_message(chat_id, msg, reply_markup=cls.get_main_reply_keyboard(user_lang))
        return True

    @classmethod
    def _handle_callback_query(cls, db: Session, cb: Dict[str, Any]) -> bool:
        """Handle interactive inline keyboard button clicks."""
        cb_id = str(cb.get("id"))
        data = str(cb.get("data", ""))
        message = cb.get("message", {})
        chat_id = str(message.get("chat", {}).get("id"))
        user = db.query(User).filter(User.telegram_chat_id == chat_id).first()
        dash_url = settings.DASHBOARD_URL.rstrip("/")

        if not user:
            cls.answer_callback_query(cb_id, "Please link your account first")
            cls.send_message(chat_id, cls._t("unlinked_msg", "en", dash_url=dash_url))
            return True

        user_lang = user.language or "en"
        cls.answer_callback_query(cb_id)

        if data == "menu:top":
            return cls._process_top_command(db, user, chat_id, user_lang, dash_url)
        elif data == "menu:digest":
            return cls._process_digest_command(db, user, chat_id, user_lang, dash_url)
        elif data == "menu:sets":
            return cls._process_sets_command(db, user, chat_id, user_lang, dash_url)
        elif data == "menu:explain":
            cls.send_message(chat_id, cls._t("explain_prompt", user_lang), reply_markup=cls.get_main_reply_keyboard(user_lang))
            return True
        elif data == "menu:status":
            return cls._process_status_command(db, user, chat_id, user_lang, dash_url)
        elif data == "menu:lang":
            cls.send_message(chat_id, cls._t("choose_language", user_lang), reply_markup=cls.get_language_inline_keyboard())
            return True
        elif data == "menu:help":
            cls.send_message(chat_id, cls._t("help", user_lang, dash_url=dash_url), reply_markup=cls.get_main_reply_keyboard(user_lang))
            return True
        elif data == "menu:back":
            cls.send_message(chat_id, cls._t("menu_header", user_lang), reply_markup=cls.get_inline_menu(user_lang, dash_url))
            return True
        elif data.startswith("lang:"):
            new_lang = data.replace("lang:", "").strip().lower()
            if new_lang in ("ru", "en", "de", "fi", "ka"):
                user.language = new_lang
                db.commit()
                cls.send_message(
                    chat_id,
                    cls._t("lang_updated", new_lang, lang=new_lang),
                    reply_markup=cls.get_main_reply_keyboard(new_lang)
                )
            return True
        elif data.startswith("set:"):
            set_id = data.replace("set:", "").strip()
            target_set = db.query(ChannelSet).filter(ChannelSet.id == set_id, ChannelSet.user_id == user.id).first()
            if target_set:
                user.active_set_id = target_set.id
                db.commit()
                cls.send_message(chat_id, cls._t("set_switched", user_lang, name=target_set.name), reply_markup=cls.get_main_reply_keyboard(user_lang))
            return True

        return True

    @classmethod
    def handle_webhook_update(cls, db: Session, update: Dict[str, Any]) -> bool:
        """Process incoming Telegram message, command, or deep-linking binding with strict user language output."""
        # 1. Handle callback query (inline buttons)
        callback_query = update.get("callback_query")
        if callback_query:
            return cls._handle_callback_query(db, callback_query)

        message = update.get("message", {})
        if not message:
            return True

        chat_id = str(message.get("chat", {}).get("id"))
        raw_text = message.get("text", "").strip()
        text = raw_text.lower()
        tg_client_lang = (message.get("from", {}).get("language_code") or "").split("-")[0].lower()
        default_lang = tg_client_lang if tg_client_lang in ("ru", "en", "de", "fi", "ka") else (settings.DEFAULT_LANGUAGE or "en")

        # 2. Check if user is already linked
        user = db.query(User).filter(User.telegram_chat_id == chat_id).first()

        LogService.log_system_event(
            category="telegram",
            action=raw_text.split()[0] if raw_text else "update",
            message=f"Telegram message: '{raw_text[:80]}' (chat_id: {chat_id})",
            user_id=user.id if user else None,
            user_email=user.email if user else None,
            details=update,
            db=db
        )

        # 3. Check for binding code (either in /start <token> or sent directly as code)
        link_code_candidate = None
        if raw_text.startswith("/start"):
            parts = raw_text.split()
            if len(parts) > 1:
                link_code_candidate = parts[1].strip().strip("`'\"#")

        if not link_code_candidate:
            for token in raw_text.split():
                clean = token.strip().strip("`'\"#")
                if len(clean) >= 12 and len(clean) <= 36:
                    link_code_candidate = clean
                    break

        dash_url = settings.DASHBOARD_URL.rstrip("/")

        if link_code_candidate:
            clean_code = link_code_candidate.strip().lower()
            target_user = (
                db.query(User)
                .filter(func.lower(User.telegram_link_code) == clean_code)
                .first()
            )
            if target_user:
                target_user.telegram_chat_id = chat_id
                target_user.telegram_link_code = None
                user_lang = target_user.language or default_lang
                target_user.language = user_lang
                db.commit()
                db.refresh(target_user)
                cls.send_message(
                    chat_id,
                    cls._t("account_linked", user_lang, email=target_user.email, dash_url=dash_url),
                    reply_markup=cls.get_main_reply_keyboard(user_lang)
                )
                cls.send_message(
                    chat_id,
                    cls._t("menu_header", user_lang),
                    reply_markup=cls.get_inline_menu(user_lang, dash_url)
                )
                return True
            else:
                cls.send_message(
                    chat_id,
                    cls._t("invalid_code", default_lang, dash_url=dash_url)
                )
                return True

        # If user is not yet bound
        if not user:
            if raw_text.startswith("/start"):
                cls.send_message(
                    chat_id,
                    cls._t("unlinked_start", default_lang, dash_url=dash_url)
                )
                return True

            cls.send_message(
                chat_id,
                cls._t("unlinked_msg", default_lang, dash_url=dash_url)
            )
            return True

        # User is authenticated! Resolve user's explicit language
        user_lang = user.language or default_lang

        if raw_text.startswith("/start"):
            cls.send_message(
                chat_id,
                cls._t("welcome_back", user_lang, email=user.email),
                reply_markup=cls.get_main_reply_keyboard(user_lang)
            )
            cls.send_message(
                chat_id,
                cls._t("menu_header", user_lang),
                reply_markup=cls.get_inline_menu(user_lang, dash_url)
            )
            return True

        # Check for /menu command or Menu button clicks
        if text in (
            "/menu", "menu", "меню",
            "📋 главное меню", "📋 main menu", "📋 hauptmenü", "📋 päävalikko", "📋 მთავარი მენიუ"
        ):
            cls.send_message(
                chat_id,
                cls._t("menu_header", user_lang),
                reply_markup=cls.get_inline_menu(user_lang, dash_url)
            )
            return True

        if text in ("/help", "помощь", "help", "❓ помощь", "❓ help", "❓ hilfe", "❓ ohje", "❓ დახმარება"):
            cls.send_message(
                chat_id,
                cls._t("help", user_lang, dash_url=dash_url),
                reply_markup=cls.get_main_reply_keyboard(user_lang)
            )
            return True

        elif text in (
            "/digest", "дайджест", "digest",
            "📢 ai-дайджест", "📢 ai digest", "📢 ki-digest", "📢 tekoäly-kooste", "📢 ai დაიჯესტი"
        ):
            return cls._process_digest_command(db, user, chat_id, user_lang, dash_url)

        elif text in (
            "/sets", "наборы", "sets",
            "📁 наборы каналов", "📁 channel sets", "📁 kanal-sets", "📁 kanavasetit", "📁 არხების ნაკრები"
        ):
            return cls._process_sets_command(db, user, chat_id, user_lang, dash_url)

        elif raw_text.startswith("/set "):
            arg = raw_text.replace("/set ", "").strip()
            sets = db.query(ChannelSet).filter(ChannelSet.user_id == user.id).all()
            target_set = None
            if arg.isdigit():
                idx = int(arg) - 1
                if 0 <= idx < len(sets):
                    target_set = sets[idx]
            else:
                for s in sets:
                    if s.name.lower() == arg.lower():
                        target_set = s
                        break

            if target_set:
                user.active_set_id = target_set.id
                db.commit()
                cls.send_message(chat_id, cls._t("set_switched", user_lang, name=target_set.name), reply_markup=cls.get_main_reply_keyboard(user_lang))
            else:
                cls.send_message(chat_id, cls._t("set_not_found", user_lang))
            return True

        elif text in (
            "/lang", "язык", "lang", "language",
            "🌐 сменить язык", "🌐 change language", "🌐 sprache", "🌐 kieli", "🌐 ენის შეცვლა"
        ):
            cls.send_message(
                chat_id,
                cls._t("choose_language", user_lang),
                reply_markup=cls.get_language_inline_keyboard()
            )
            return True

        elif raw_text.startswith("/lang "):
            parts = raw_text.split()
            if len(parts) > 1 and parts[1].lower() in ("ru", "en", "de", "fi", "ka"):
                new_lang = parts[1].lower()
                user.language = new_lang
                db.commit()
                cls.send_message(
                    chat_id,
                    cls._t("lang_updated", new_lang, lang=new_lang),
                    reply_markup=cls.get_main_reply_keyboard(new_lang)
                )
            else:
                cls.send_message(chat_id, cls._t("lang_help", user_lang))
            return True

        elif text in (
            "/top", "топ", "top",
            "📊 топ-10 видео", "📊 top 10 videos", "📊 top 10 videot", "📊 ტოპ 10 ვიდეო"
        ):
            return cls._process_top_command(db, user, chat_id, user_lang, dash_url)

        elif text in (
            "/explain", "разбор", "explain",
            "🧠 ai-разбор", "🧠 ai breakdown", "🧠 ki-analyse", "🧠 tekoäly-analyysi", "🧠 ai ანალიზი"
        ):
            cls.send_message(
                chat_id,
                cls._t("explain_prompt", user_lang),
                reply_markup=cls.get_main_reply_keyboard(user_lang)
            )
            return True

        elif raw_text.startswith("/explain"):
            arg = raw_text.replace("/explain", "").strip()
            if not arg:
                cls.send_message(chat_id, cls._t("explain_need_number", user_lang))
                return True

            active_set_id = user.active_set_id
            if not active_set_id:
                cls.send_message(chat_id, cls._t("explain_choose_set", user_lang))
                return True

            videos = AnalyticsService.get_set_enriched_videos(db, user.id, active_set_id, limit=20)
            target_video = None
            if arg.isdigit():
                idx = int(arg) - 1
                if 0 <= idx < len(videos):
                    target_video = videos[idx]

            if not target_video:
                cls.send_message(chat_id, cls._t("explain_not_found", user_lang))
                return True

            gemini_key = decrypt_secret(user.gemini_api_key_encrypted)
            explanation = GeminiService.explain_video_success(
                video_data=target_video,
                target_language=user_lang,
                gemini_api_key=gemini_key,
                user_id=user.id,
                user_email=user.email,
                db=db
            )

            header = cls._t("explain_header", user_lang)
            metrics_line = cls._t(
                "explain_metrics_label",
                user_lang,
                views=target_video.get("view_count", 0),
                outlier=target_video.get("outlier_score", 1.0),
                velocity=target_video.get("velocity_vph", 0)
            )
            verdict_lbl = cls._t("explain_verdict", user_lang)
            hook_lbl = cls._t("explain_hook", user_lang)
            trend_lbl = cls._t("explain_trend", user_lang)
            takeaway_lbl = cls._t("explain_takeaway", user_lang)

            msg = (
                f"{header}\n"
                f"«{target_video.get('title')}» ({target_video.get('channel_title')})\n\n"
                f"{metrics_line}\n\n"
                f"{verdict_lbl}\n{explanation.get('verdict', '')}\n\n"
                f"{hook_lbl}\n{explanation.get('hook_analysis', '')}\n\n"
                f"{trend_lbl}\n{explanation.get('trend_alignment', '')}\n\n"
                f"{takeaway_lbl}\n{explanation.get('actionable_takeaway', '')}"
            )
            cls.send_message(chat_id, msg, reply_markup=cls.get_main_reply_keyboard(user_lang))
            return True

        elif text in (
            "/status", "статус", "status",
            "⚙️ статус ключей", "⚙️ status", "⚙️ tila", "⚙️ სტატუსი"
        ):
            return cls._process_status_command(db, user, chat_id, user_lang, dash_url)

        else:
            cls.send_message(chat_id, cls._t("unknown_cmd", user_lang), reply_markup=cls.get_main_reply_keyboard(user_lang))
            return True
