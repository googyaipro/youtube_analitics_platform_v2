# 🎬 YouTube Analytics & Competitor Intelligence Platform (Multi-Tenant SaaS)

Масштабируемая мультитенантная платформа для глубокого анализа YouTube-каналов, мониторинга конкурентов и обнаружения виральных трендов. Развернута в **Docker (Dokploy)** с нулевой привязкой к платным облачным сервисам (**Zero Cloud Lock-in**) благодаря модели **BYOK (Bring Your Own Keys)**, поддержке **5 языков (i18n)**, независимым наборам каналов с персональными планировщиками и интеграции с **Telegram**.

* **Веб-интерфейс (Streamlit):** [https://yap.oxyjet.win](https://yap.oxyjet.win)
* **API и вебхуки (FastAPI):** [https://api.yap.oxyjet.win](https://api.yap.oxyjet.win)
* **Документация Swagger UI:** [https://api.yap.oxyjet.win/docs](https://api.yap.oxyjet.win/docs)

---

## 🏛️ Архитектура системы (Dokploy / Docker Compose)

```mermaid
flowchart TD
    subgraph Clients ["Интерфейсы взаимодействия"]
        Web["💻 Веб-интерфейс Streamlit (yap.oxyjet.win)\n• Авторизация JWT, мультиязычность (5 языков)\n• Выбор и переключение наборов каналов\n• KPI, Топ видео, бейджи виральности\n• AI-разбор успеха ролика (Gemini)\n• Интерактивный чат с AI-Аналитиком\n• Управление персональными API ключами (BYOK)"]
        TG["📱 Telegram Бот (@youtubeanalitics0_bot)\n• Привязка аккаунта по Deep Link (/start token)\n• Команды: /sets, /top, /explain, /lang, /status\n• Персональные утренние дайджесты по расписанию"]
    end

    subgraph TraefikProxy ["Dokploy Edge Router (Traefik v3)"]
        Router["Traefik Reverse Proxy\n• Автоматические SSL-сертификаты Let's Encrypt\n• Маршрутизация yap.oxyjet.win -> Dashboard\n• Маршрутизация api.yap.oxyjet.win -> Backend"]
    end

    subgraph DockerCompose ["Изолированный стек Docker (Dokploy)"]
        subgraph SvcBackend ["Сервис: yap_backend (FastAPI / Python 3.12)"]
            Auth["JWT Auth & Security (bcrypt, pyjwt)"]
            BYOK["AES-256 Fernet Encryption (Хранение ключей)"]
            Analytics["ANSI SQL Analytics Engine (Оконные функции)"]
            Dispatcher["Timezone-Aware Scheduler Dispatcher"]
            TGBot["Telegram Webhook & Async Worker"]
            APIEndpoints["REST API (/auth, /user, /channel-sets, /channels, /videos, /analyze, /cron)"]
        end

        subgraph SvcDashboard ["Сервис: yap_dashboard (Streamlit)"]
            I18n["i18n Engine (ru, en, de, fi, ka)"]
            UI["Streamlit Multi-Page UI"]
        end

        subgraph SvcDB ["Сервис: yap_postgres (PostgreSQL 16)"]
            PG[("PostgreSQL 16 Alpine\n• users\n• channel_sets\n• channels\n• video_metrics")]
        end
    end

    subgraph ExternalBYOK ["Внешние API пользователей (BYOK — 0.00$ серверных затрат)"]
        YT_API["YouTube Data API v3\n(Личные ключи пользователей: 10k квот/день бесплатно)"]
        AI_Studio["Google AI Studio (Gemini 2.5 Flash)\n(Личные ключи пользователей: 15 RPM бесплатно)"]
        TG_API["Telegram Bot API\n(Отправка дайджестов и уведомлений)"]
    end

    Web --> Router
    TG --> Router
    Router --> SvcDashboard
    Router --> SvcBackend

    SvcDashboard <-- "HTTP REST API + Bearer JWT" --> SvcBackend
    SvcBackend <--> PG

    SvcBackend -->|"Запросы метаданных с личным ключом"| YT_API
    SvcBackend -->|"Генерация отчетов и разборов с личным ключом"| AI_Studio
    SvcBackend -->|"Доставка дайджестов"| TG_API
```

---

## 💎 Ключевые возможности и архитектурные решения

### 1. Zero Cloud Lock-in и архитектура BYOK (Bring Your Own Keys)
* **Никакой привязки к Google Cloud (Cloud Run, BigQuery, Firestore, Cloud Tasks)**: система полностью упакована в стандартный Docker Compose и развертывается на любом VPS/VDS через Dokploy.
* **Нулевая себестоимость инфраструктуры**:
  * Каждый пользователь указывает свой собственный **YouTube Data API v3 Key** (10,000 бесплатных единиц квоты в сутки от Google).
  * Каждый пользователь указывает свой собственный **Gemini API Key** из Google AI Studio (бесплатный тариф: 15 запросов в минуту для модели `gemini-2.5-flash`).
  * Владелец сервера платит **0.00$** за квоты YouTube и генерацию AI.
* **Безопасность AES-256 (Fernet)**:
  * Ключи шифруются симметричным алгоритмом AES-256 перед записью в PostgreSQL.
  * Расшифровка происходит исключительно в оперативной памяти в момент обращения к YouTube или Gemini API.
  * В интерфейсе предусмотрены кнопки мгновенной проверки валидности обоих ключей с выводом статуса.

### 2. Мультитенантность и наборы каналов (Workspaces)
* **Изолированные рабочие пространства**: каждый пользователь может создавать произвольное количество тематических наборов (например: *«Tech & AI»*, *«Crypto & Web3»*, *«SEO & Marketing»*).
* **Персональный планировщик дайджестов (Scheduler)**:
  * Для каждого набора задается свое время (например, `12:00`), часовой пояс (`Europe/Helsinki`, `Europe/Berlin`, `Asia/Tbilisi`, `UTC` и т.д.) и дни недели (`mon,tue,wed,thu,fri`).
  * Диспетчер [`SchedulerService`](file:///home/xgelionix/My_Code/Gcloud/youtube-analitics-platform/backend/services/scheduler_service.py) учитывает часовые пояса и сезонный перевод часов (Daylight Saving Time), запуская сбор данных и генерацию утреннего отчета строго по локальному времени пользователя.

### 3. Высокопроизводительный аналитический движок (SQL Window Functions)
Вместо дорогостоящего DWH в BigQuery аналитический движок реализован на чистом ANSI SQL с оконными функциями, работающими в PostgreSQL (и SQLite для локального тестирования):
* 🚀 **Множитель к норме (Outlier Score)**:
  $$\text{Outlier Score} = \frac{\text{Просмотры ролика}}{\text{Средняя норма просмотров автора}}$$
  Выявляет вирусные аномалии, отсекая базовый трафик каналов-миллионников.
* ⚡ **Скорость набора просмотров (Velocity VPH)**:
  $$\text{VPH} = \frac{\text{Просмотры}}{\text{Количество часов с момента публикации}}$$
* 💬 **Коэффициент вовлеченности (Engagement Rate %)**:
  $$\text{ER} = \frac{\text{Лайки} + \text{Комментарии}}{\text{Просмотры}} \times 100\%$$
* 🏷️ **Автоматические бейджи**: `🚀 Хит 3.2x`, `📈 Выше нормы (1.7x)`, `⚡ 540 просм/ч`, `💬 ER 2.8%`.
* **Время отклика**: расчет метрик по сотням видео выполняется за **2–5 мс**.

### 4. Полная мультиязычность (i18n — 5 языков)
Платформа изначально спроектирована для международной аудитории и поддерживает 5 языков:
* 🇷🇺 **Русский** (`ru`)
* 🇬🇧 **Английский** (`en`)
* 🇩🇪 **Немецкий** (`de`)
* 🇫🇮 **Финский** (`fi`)
* 🇬🇪 **Грузинский** (`ka`)

Локализация распространяется на:
1. Веб-интерфейс дашборда Streamlit ([`dashboard/locales/`](file:///home/xgelionix/My_Code/Gcloud/youtube-analitics-platform/dashboard/locales)).
2. Промпты и аналитические ответы модели Gemini (глубокий разбор видео, ежедневный дайджест, интерактивный AI-аналитик).
3. Сообщения, команды и отчеты Telegram-бота.

### 5. Мультитенантный Telegram-бот с Deep Linking
* **Привязка аккаунта в один клик**: в личном кабинете на `https://yap.oxyjet.win` генерируется персональная ссылка вида `https://t.me/youtubeanalitics0_bot?start=<token>`. При переходе бот связывает Telegram Chat ID с профилем пользователя.
* **Команды бота**:
  * `/sets` — список наборов каналов пользователя с расписанием;
  * `/set <номер>` — переключение активного набора;
  * `/top` — топ-10 роликов текущего набора с факторами виральности и бейджами;
  * `/explain <номер>` — глубокий AI-разбор факторов успеха ролика через Gemini;
  * `/lang <ru|en|de|fi|ka>` — быстрая смена языка отчетов;
  * `/status` — статус привязанных API-ключей и планировщика;
  * `/help` — список возможностей.
* **Асинхронная обработка**: вебхук отвечает Telegram за `< 20 мс`, а обработка команд выполняется в фоне через FastAPI `BackgroundTasks`.

---

## 📁 Структура репозитория

```
youtube-analitics-platform/
├── backend/
│   ├── api/
│   │   └── v1/
│   │       ├── endpoints/
│   │       │   ├── auth.py                # POST /auth/register, /auth/login, GET /auth/me
│   │       │   ├── user.py                # PUT /user/keys, POST /user/verify-key, POST /user/telegram-link
│   │       │   ├── channel_sets.py        # CRUD для наборов каналов, /activate, /sync
│   │       │   ├── channels.py            # GET /channels, POST /channels (BYOK), DELETE /channels
│   │       │   ├── videos.py              # GET /videos, GET /videos/kpis, GET /{id}/explain
│   │       │   ├── analyze.py             # POST /analyze (Интерактивный диалог с AI-Аналитиком)
│   │       │   ├── cron.py                # POST /cron/dispatch-schedules (Ежечасный запуск)
│   │       │   └── telegram.py            # POST /telegram/webhook, POST /telegram/setup-webhook
│   │       └── router.py                  # Центральный роутер API v1
│   ├── core/
│   │   ├── database.py                    # SQLAlchemy Engine, Session, авто-фоллбэк на SQLite
│   │   └── security.py                    # Хэширование bcrypt, JWT (pyjwt), AES-256 (Fernet)
│   ├── models/
│   │   ├── user.py                        # Модель User (ключи, настройки, telegram_chat_id)
│   │   ├── channel_set.py                 # Модель ChannelSet (расписание, часовой пояс, дни)
│   │   ├── channel.py                     # Модель Channel (привязка к user и set)
│   │   └── video_metric.py                # Модель VideoMetric (снимки просмотров и реакций)
│   ├── schemas/                           # Pydantic DTO схемы запросов и ответов
│   │   ├── auth.py
│   │   ├── channel_set.py
│   │   ├── channel.py
│   │   └── video.py
│   ├── services/
│   │   ├── youtube_service.py             # Клиент YouTube Data API v3 (чистый HTTP, UU-плейлисты)
│   │   ├── gemini_service.py              # Google AI Studio Gemini API (мультиязычные промпты)
│   │   ├── analytics_service.py           # SQL-движок факторного анализа и KPI
│   │   ├── scheduler_service.py           # Диспетчер расписаний с учетом таймзон
│   │   └── telegram_service.py            # Обработчик команд бота и отправка дайджестов
│   └── main.py                            # Инициализация FastAPI приложения и CORS
├── dashboard/
│   ├── 0_🏠_Главная.py                     # Главный экран: KPI, селектор наборов, топ видео, AI-разбор
│   ├── locales/                           # Словари переводов (i18n)
│   │   ├── ru.json                        # Русский язык
│   │   ├── en.json                        # Английский язык
│   │   ├── de.json                        # Немецкий язык
│   │   ├── fi.json                        # Финский язык
│   │   └── ka.json                        # Грузинский язык
│   ├── pages/
│   │   ├── 1_📈_Динамика.py               # Лидерборды каналов и матрица виральности (Scatter)
│   │   ├── 2_💬_AI_Аналитик.py            # Чат с Gemini 2.5 Flash по видео конкурентов
│   │   ├── 3_⚙️_Наборы_Каналов.py         # Управление наборами, расписанием и каналами
│   │   └── 4_🔑_Профиль_и_API.py          # Настройка ключей BYOK, проверка и привязка Telegram
│   └── utils/
│       ├── api_client.py                  # HTTP-клиент к FastAPI бэкенду с Bearer JWT
│       ├── auth_ui.py                     # Компоненты авторизации и профиля Streamlit
│       └── i18n.py                        # Утилита загрузки локалей и переключения языков
├── docker-compose.yml                     # Стек для деплоя в Dokploy (Postgres + Backend + Dashboard)
├── Dockerfile                             # Контейнер бэкенда (Python 3.12-slim)
├── Dockerfile.dashboard                   # Контейнер дашборда (Streamlit)
├── requirements.txt                       # Зависимости проекта
├── .env.example                           # Шаблон переменных окружения
└── tests/
    └── test_multiusers.py                 # Комплексный набор тестов (JWT, AES, SQL, i18n, Telegram)
```

---

## ⚙️ Переменные окружения (.env)

| Переменная | Описание | Пример значения |
| :--- | :--- | :--- |
| `POSTGRES_USER` | Пользователь базы данных PostgreSQL | `yap_user` |
| `POSTGRES_PASSWORD` | Пароль к базе данных | `secure_pg_password_2026` |
| `POSTGRES_DB` | Имя базы данных | `youtube_analytics` |
| `DATABASE_URL` | Строка подключения SQLAlchemy | `postgresql://yap_user:pass@postgres:5432/youtube_analytics` |
| `SECRET_KEY` | Секретный ключ для подписи JWT-токенов (32 байта) | `c92739f75470d02bce0eb8e652fb6a256a5dbd4e8b35...` |
| `ENCRYPTION_KEY` | Ключ Fernet (AES-256 base64) для шифрования ключей BYOK | `X9s65f-4v-T7t2Zg3B7qjV6G4j0kE9h1pL5y2rA4uB8=` |
| `TELEGRAM_BOT_TOKEN` | Токен Telegram-бота от BotFather | `8824791628:AAGcvPcC3lCZ3SziCO4fpqVoOhYjEdoudh8` |
| `TELEGRAM_BOT_USERNAME` | Имя пользователя Telegram-бота (без `@`) | `youtubeanalitics0_bot` |
| `TELEGRAM_WEBHOOK_SECRET` | Секретный токен для проверки вебхука Telegram | `216e54ccb062bce4dbe9cc9e2eced4d2` |
| `DOKPLOY_WEB_DOMAIN` | Домен веб-интерфейса | `yap.oxyjet.win` |
| `DOKPLOY_API_DOMAIN` | Домен REST API и вебхука | `api.yap.oxyjet.win` |
| `BACKEND_API_URL` | Внутренний или публичный URL API для Streamlit | `http://backend:8080/api/v1` |

---

## 🚀 Развёртывание в Dokploy (Production)

### Шаг 1. Создание Compose Stack в Dokploy
1. Откройте панель **Dokploy** на вашем сервере.
2. Создайте новый проект или перейдите в существующий, нажмите **Create Service** -> **Compose**.
3. Выберите репозиторий `git@github.com:xGelionix/youtube_analitics_platform.git` и укажите ветку **`multiusers`**.

### Шаг 2. Настройка переменных окружения
В разделе **Environment** скопируйте значения из [`.env.example`](file:///home/xgelionix/My_Code/Gcloud/youtube-analitics-platform/.env.example) и сгенерируйте надежные ключи:
```bash
# Генерация SECRET_KEY
openssl rand -hex 32

# Генерация ENCRYPTION_KEY
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### Шаг 3. Деплой
Нажмите **Deploy**. Dokploy автоматически:
1. Запустит базу данных `yap_postgres` и дождется успешного прохождения healthcheck.
2. Соберет и запустит контейнеры `yap_backend` и `yap_dashboard`.
3. Traefik автоматически выпустит бесплатные SSL-сертификаты Let's Encrypt для:
   * `https://yap.oxyjet.win`
   * `https://api.yap.oxyjet.win`

### Шаг 4. Настройка расписания в Dokploy Cron
Для работы персональных дайджестов добавьте в Dokploy Cron ежечасный триггер:
* **Расписание (Cron):** `0 * * * *` (в начале каждого часа)
* **Команда:**
  ```bash
  curl -X POST -H "x-cron-secret: $TELEGRAM_WEBHOOK_SECRET" http://backend:8080/api/v1/cron/dispatch-schedules
  ```

---

## 💻 Локальный запуск для разработки

```bash
# 1. Клонирование и переход на ветку multiusers
git clone https://github.com/xGelionix/youtube_analitics_platform.git
cd youtube-analitics-platform
git checkout multiusers

# 2. Создание виртуального окружения
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. Настройка переменных окружения
cp .env.example .env

# 4. Запуск FastAPI бэкенда (порт 8000)
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

# 5. Запуск Streamlit дашборда (в отдельном терминале, порт 8501)
streamlit run dashboard/0_🏠_Главная.py --server.port 8501
```

* Веб-интерфейс: `http://localhost:8501`
* Документация FastAPI: `http://localhost:8000/docs`

---

## 🧪 Автоматическое тестирование

В проект включен комплексный набор тестов [`tests/test_multiusers.py`](file:///home/xgelionix/My_Code/Gcloud/youtube-analitics-platform/tests/test_multiusers.py):
* Хэширование паролей bcrypt и создание/валидация JWT;
* Симметричное шифрование и расшифровка ключей BYOK по AES-256;
* Создание пользователей и изолированных наборов каналов;
* Оконные функции SQL аналитического движка и расчет аномалий;
* Полнота локализации по всем 5 языкам (`ru`, `en`, `de`, `fi`, `ka`);
* Обработка команд Telegram-бота и deep-linking привязка;
* Интеграционные тесты REST API (FastAPI TestClient).

Запуск тестов:
```bash
pytest tests/test_multiusers.py -v
```
