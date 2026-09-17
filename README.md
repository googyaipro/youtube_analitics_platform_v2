# 🎬 YouTube Analytics & Competitor Intelligence Platform

Масштабируемая serverless-платформа аналитики YouTube-каналов и мониторинга конкурентов на стеке **Google Cloud Platform (GCP)** с искусственным интеллектом **Vertex AI Gemini 3.8 Flash**, DWH в **BigQuery**, кэшем в **Firestore Native**, очередями **Cloud Tasks**, интерактивным дашбордом на **Streamlit** и безопасной изолированной песочницей кода **Code Sandbox**.

---

## 🏛️ Продакшн-архитектура (Google Cloud)

```mermaid
flowchart TD
    subgraph Clients ["Интерфейсы взаимодействия"]
        TG["📱 Telegram Бот (@youtubeanalitics0_bot)\n• Команды: /help, /explain, /list, /users\n• Безопасность: Whitelist Access Control\n• Утренние алерты и AI-разборы"]
        Web["💻 Streamlit Дашборд\n• 0_🏠_Главная (KPI, Топ роликов, Фильтры)\n• 1_📈_Динамика (Лидерборды, Рост)\n• 2_💬_AI-Аналитик (Диалог с Plotly)\n• 3_⚙️_Управление (Каналы, Пользователи TG)"]
    end

    subgraph Trigger ["Оркестрация и Очереди"]
        Cron["⏰ Cloud Scheduler\n(Ежедневный сбор метрик 08:00 UTC)"]
        CT["📬 Cloud Tasks (telegram-tasks)\n(Очередь задач TG + Dedicated CPU)"]
    end

    subgraph CloudRun ["Google Cloud Run (Serverless Microservices)"]
        subgraph SvcBackend ["Сервис 1: youtube-analyst-backend (FastAPI)"]
            FastAPI["FastAPI Core"]
            Hook["/api/telegram/webhook (15ms ACK)"]
            TaskWorker["/api/tasks/process-telegram-message (Dedicated CPU)"]
            CronRoute["/api/cron/track-competitors"]
            APIVideos["/api/videos & /api/videos/{id}/explain"]
            APIAnalyze["/api/analyze (AI Reasoning)"]
            APIComp["/api/competitors (CRUD)"]
            Orchestrator["Root Agent Orchestrator"]
            
            FastAPI --> Hook & TaskWorker & CronRoute & APIVideos & APIAnalyze & APIComp
            Hook -->|15ms Enqueue| CT
            CT -->|HTTP POST| TaskWorker
            TaskWorker & APIAnalyze --> Orchestrator
        end

        subgraph SvcDashboard ["Сервис 2: youtube-dashboard (Streamlit)"]
            StreamlitApp["Multi-Page Streamlit App\n(Аналитика, Факторы виральности, AI-разбор)"]
        end

        subgraph SvcSandbox ["Сервис 3: code-sandbox (512MB RAM, Internal)"]
            Runner["Изолированный Python Runner\n(Matplotlib PNG для TG / Plotly JSON для Web)"]
        end
    end

    subgraph GoogleCloud ["Инфраструктура Google Cloud"]
        FS[("Firestore (Native Mode)\n(Горячий кэш TTL 24h + Whitelist подписчиков)")]
        BQ[("Google BigQuery\n(video_metrics, channels, excluded_channels, views)")]
        Vertex["Vertex AI (Multi-Region US)\n(Gemini 3.8 Flash: Thinking + JSON Reasoning)"]
        YT["YouTube Data API v3\n(Uploads Playlist UU...: 1 unit quota)"]
    end

    TG <-->|HTTPS Webhook (Secret Token)| Hook
    TaskWorker -->|sendPhoto / sendMessage| TG
    Web <-->|REST API| SvcBackend
    Cron -->|OIDC Auth POST| CronRoute
    
    Orchestrator <-->|Prompting & Structured Output| Vertex
    Orchestrator <-->|Key-Value Hot Cache| FS
    Orchestrator <-->|DWH Window SQL & Views| BQ
    Orchestrator <-->|1 unit quota calls| YT
    Orchestrator <-->|Safe Code Execution| SvcSandbox
```

---

## 💎 Ключевые возможности и стандарты

### 1. Ядро искусственного интеллекта — Vertex AI Gemini 3.8 Flash
* **Мультирегиональный эндпоинт (`us`)**: Запросы направляются через `aiplatform.googleapis.com` в Multi-Region US с минимальной задержкой и высокой доступностью.
* **Нативный режим рассуждений (Thinking Mode)**: Модель генерирует скрытые цепочки рассуждений (`thoughtSignature`), гарантируя точность выводов и структурированный JSON без галлюцинаций.
* **Генерация исполняемого кода**: Создание безопасного Python-кода для рендеринга визуализаций в песочнице.

### 2. Движок факторного анализа виральности роликов (Success Factor Engine)
Для каждого видео в реальном времени вычисляются объективные факторы популярности:
* 🚀 **Хайп-фактор (Outlier Score)**:
  $$\text{Outlier Score} = \frac{\text{Просмотры ролика}}{\text{Медианная норма просмотров канала}}$$
  Отделяет органические просмотры крупного канала от вирусных взрывов (например, хит Julian Goldie SEO набрал **5.81x** к норме канала).
* ⚡ **Скорость набора (Velocity VPH)**: Количество просмотров в час с момента релиза ($\text{views} / \text{hours}$).
* 💬 **Вовлеченность аудитории (ER %)**: $(\text{лайки} + \text{комментарии}) / \text{просмотры} \times 100\%$.
* 🏷️ **Бейджи виральности**: Автоматические теги (`🚀 Хит 3.5x`, `⚡ 803 просм/ч`, `💬 ER 1.2%`).
* 🧠 **AI-Разбор успеха (Gemini 3.8 Flash)**:
  * **Вердикт**: Краткий вывод, почему именно это видео взлетело.
  * **Крючки темы и заголовка**: Разбор психологии кликабельности, интриги и триггеров.
  * **Оседланный тренд / Инфоповод**: Почему тема актуальна прямо сейчас.
  * **Формула успеха (Takeaway)**: Практические рекомендации, как повторить результат на своем канале.

### 3. Telegram-бот с безопасным доступом (`@youtubeanalitics0_bot`)
* **Мгновенный ACK за 15 мс**: Вебхук проверяет секретный токен (`x-telegram-bot-api-secret-token`) и ставит задачу в **Google Cloud Tasks**, защищая Cloud Run от CPU Throttling и сохраняя Scale-to-Zero.
* **Контроль доступа (Whitelist)**: Доступ открыт только авторизованным Telegram ID и Username (`TELEGRAM_ALLOWED_USERS`, `TELEGRAM_ADMIN_CHAT_ID`). Попытки входа неавторизованных пользователей логируются с уведомлением администратора.
* **Меню команд (Telegram Menu Button)**:
  * `/help` — Справка по возможностям и командам
  * `/explain [номер|название]` — Глубокий AI-разбор факторов успеха любого видео
  * `/list` — Список отслеживаемых каналов и их метрики
  * `/users` — Список зарегистрированных пользователей и их статусы (для администратора)
  * `/add @handle` — Добавление нового канала в мониторинг
  * `/delete @handle` — Удаление канала из мониторинга
* **Динамическое распознавание каналов**: Бот понимает названия каналов из базы данных (*«Мастодонт»*, *«ИИшенка»*, *«Jack Roberts»*) даже без символа `@`.

### 4. Веб-дашборд Streamlit
* **0_🏠_Главная.py**: Сводные KPI, блок «🔥 Топ роликов по просмотрам» с фильтром по каналу, выбором лимита (10, 20, 30, 50), бейджами лидеров, ссылками на YouTube и интерактивной карточкой **«🔍 AI-Разбор факторов успеха ролика»**.
* **1_📈_Динамика.py**: Лидерборды каналов по подписчикам и суммарным просмотрам на базе BigQuery View без расхода квот.
* **2_💬_AI_Аналитик.py**: Интерактивный диалог с Gemini 3.8 Flash и рендеринг графиков Plotly в браузере.
* **3_⚙️_Управление_каналами.py**: Добавление каналов, Tombstone-удаление и аудит пользователей Telegram.

### 5. Оптимизация квот и производительность хранилища
* **Экономия квоты YouTube на 99%**: Загрузки собираются через плейлист `UU...` (`playlistItems().list`) — расход **1 unit** вместо 100 units.
* **Firestore Native Mode**: Горячий кэш метаданных с TTL 24 часа и откликом 30–50 мс.
* **Tombstone Pattern в BigQuery**: Безопасное мгновенное удаление каналов через таблицу `excluded_channels` в обход ограничений streaming buffer BigQuery.

---

## 📁 Структура репозитория

```
youtube-analitics-platform/
├── backend/
│   ├── api/
│   │   └── v1/
│   │       ├── endpoints/
│   │       │   ├── analyze.py             # POST /api/analyze (AI-анализ + генерация кода)
│   │       │   ├── channels.py            # GET /api/channels (реестр активных каналов)
│   │       │   ├── competitors.py         # POST /api/competitors, DELETE /api/competitors/{id}
│   │       │   ├── cron.py                # POST /api/cron/track-competitors (утренний сбор)
│   │       │   ├── ingestion.py           # POST /api/ingestion/sync-channel
│   │       │   ├── tasks.py               # POST /api/tasks/process-telegram-message (Cloud Tasks)
│   │       │   ├── telegram.py            # POST /api/telegram/webhook, GET /subscribers
│   │       │   └── videos.py              # GET /api/videos, GET /kpis, GET /{id}/explain
│   │       └── router.py                  # Главный роутер API v1
│   ├── models/
│   │   ├── channel.py                     # Pydantic-модели канала и статистики
│   │   └── video.py                       # Pydantic-модели видео и метрик
│   ├── prompts/
│   │   ├── analyzer.txt                   # Системный промпт AI-аналитика
│   │   ├── morning_digest.txt             # Шаблон утреннего дайджеста
│   │   ├── telegram_welcome.txt           # Текст приветствия и справки бота
│   │   └── loader.py                      # Загрузчик текстовых промптов
│   ├── services/
│   │   ├── agent_orchestrator.py          # Корневой оркестратор запросов
│   │   ├── bigquery_service.py            # Интеграция с BigQuery, аналитические SQL и Tombstones
│   │   ├── cloud_tasks_service.py         # Создание задач в очереди Google Cloud Tasks
│   │   ├── firestore_cache.py             # Кэш в Firestore Native Mode и база подписчиков TG
│   │   ├── gemini_service.py              # Vertex AI Gemini 3.8 Flash (Multi-Region US)
│   │   ├── sandbox_client.py              # HTTP-клиент к изолированной песочнице
│   │   ├── storage_service.py             # Бэкапы сырых JSON в Google Cloud Storage
│   │   ├── telegram_bot.py                # Отправка сообщений, фото и регистрация команд
│   │   └── youtube_client.py              # Клиент YouTube Data API v3 (UU-плейлисты)
│   └── main.py                            # Точка входа FastAPI приложения
├── dashboard/
│   ├── 0_🏠_Главная.py                     # Главный экран: KPI, Топ видео, AI-Разбор успеха
│   ├── pages/
│   │   ├── 1_📈_Динамика.py               # Анализ трендов, лидерборды конкурентов
│   │   ├── 2_💬_AI_Аналитик.py            # Чат с Gemini 3.8 Flash и интерактивный Plotly
│   │   └── 3_⚙️_Управление_каналами.py    # Управление каналами и безопасность Telegram
│   └── utils/
│       └── api_client.py                  # Клиент Streamlit для связи с бэкендом
├── services/
│   └── sandbox/                           # Сервис 3: Изолированная песочница кода
│       ├── app.py                         # FastAPI сервис песочницы (POST /execute)
│       ├── runner.py                      # Песочница с ограниченным namespace и таймаутом
│       ├── Dockerfile                     # Изолированный контейнер (512MB RAM, non-root)
│       └── requirements.txt
├── sql/
│   └── ddl.sql                            # DDL BigQuery (таблицы, партиционирование, Views)
├── scripts/
│   ├── deploy_all.sh                      # Автоматический деплой всех 3 сервисов в Cloud Run
│   ├── run_dev.sh                         # Локальный запуск (FastAPI + Streamlit)
│   ├── setup_dwh.py                       # Инициализация датасета и схем BigQuery
│   └── setup_infra.sh                     # Включение API, создание очередей Cloud Tasks
├── tests/
│   └── test_backend.py                    # E2E и интеграционные тесты
├── Dockerfile                             # Dockerfile для бэкенда (FastAPI)
├── Dockerfile.dashboard                   # Dockerfile для дашборда (Streamlit)
├── requirements.txt                       # Зависимости Python (включая google-cloud-aiplatform)
└── README.md
```

---

## ⚙️ Переменные окружения (.env)

| Переменная | Описание | Пример значения |
| :--- | :--- | :--- |
| `GCP_PROJECT_ID` | Идентификатор проекта GCP | `gen-lang-client-0428255657` |
| `GCP_REGION` | Регион размещения сервисов Cloud Run | `us-central1` |
| `VERTEX_AI_REGION` | Локация эндпоинта Vertex AI для Gemini 3.8 | `us` *(Multi-Region)* |
| `GEMINI_MODEL` | Модель искусственного интеллекта | `gemini-3.8-flash` |
| `BIGQUERY_DATASET_ID` | Датасет BigQuery | `youtube_analytics` |
| `GCS_BUCKET_NAME` | Бакет для архива сырых данных | `gen-lang-client-0428255657-yt-raw-data` |
| `CLOUD_TASKS_QUEUE` | Очередь задач Cloud Tasks | `telegram-tasks` |
| `YOUTUBE_API_KEY` | Ключ YouTube Data API v3 | `AIzaSy...` |
| `TELEGRAM_BOT_TOKEN` | Токен Telegram-бота от BotFather | `8824791628:AAG...` |
| `TELEGRAM_WEBHOOK_SECRET` | Секретный токен валидации вебхука | `216e54ccb062...` |
| `TELEGRAM_ADMIN_CHAT_ID` | Chat ID главного администратора | `1522730105` |
| `TELEGRAM_ALLOWED_USERS` | Whitelist пользователей (ID или Username) | `1522730105;CyberPope` |
| `SANDBOX_SERVICE_URL` | Внутренний URL сервиса песочницы | `https://code-sandbox-...a.run.app` |
| `BACKEND_PUBLIC_URL` | Публичный HTTPS URL бэкенда | `https://youtube-analyst-backend-...a.run.app` |
| `BACKEND_API_URL` | URL API для Streamlit дашборда | `https://youtube-analyst-backend-...a.run.app/api` |

---

## 🚀 Развёртывание и запуск

### 1. Локальный запуск для разработки

```bash
# Клонирование и установка зависимостей
git clone https://github.com/xGelionix/youtube-analitics-platform.git
cd youtube-analitics-platform

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r services/sandbox/requirements.txt

# Настройка окружения
cp .env.example .env

# Запуск бэкенда и дашборда
./scripts/run_dev.sh
```

* Веб-дашборд: `http://localhost:8501`
* Документация FastAPI (Swagger): `http://localhost:8000/docs`
* Песочница: `http://localhost:8080/docs`

### 2. Развёртывание инфраструктуры в Google Cloud

```bash
# Авторизация в GCP
gcloud auth application-default login
gcloud config set project gen-lang-client-0428255657

# Инициализация инфраструктуры
./scripts/setup_infra.sh
```

Скрипт автоматически:
1. Включает сервисы `run.googleapis.com`, `cloudtasks.googleapis.com`, `firestore.googleapis.com`, `bigquery.googleapis.com`, `aiplatform.googleapis.com`, `cloudscheduler.googleapis.com`.
2. Создает очередь задач `telegram-tasks` в Cloud Tasks.
3. Включает TTL-политику Firestore для коллекции `api_cache`.
4. Разворачивает DWH-таблицы и View в BigQuery.

### 3. Деплой всех сервисов в Cloud Run

```bash
./scripts/deploy_all.sh
```

Скрипт выполняет сборку и публикацию:
* **`code-sandbox`**: Изолированная среда выполнения Python (512MB RAM).
* **`youtube-analyst-backend`**: FastAPI сервис с подключением к Gemini 3.8 Flash, BigQuery и Firestore.
* **`youtube-dashboard`**: Streamlit интерфейс с прямым подключением к бэкенду.
* **Авторегистрация вебхука Telegram** с защитным токеном и меню команд через `setMyCommands`.

---

## 🧪 Тестирование

```bash
# Запуск интеграционных и E2E тестов
pytest tests/ -v
```
