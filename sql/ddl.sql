-- =====================================================================
-- Google Cloud BigQuery DDL for YouTube Analytics Platform
-- Target Dataset: youtube_analytics
-- Target Location: europe-west1 / US (configurable)
-- =====================================================================

-- 1. Создание датасета
CREATE SCHEMA IF NOT EXISTS `youtube_analytics`
OPTIONS (location = 'US');

-- 2. Реестр отслеживаемых каналов-конкурентов
CREATE TABLE IF NOT EXISTS `youtube_analytics.competitor_channels` (
    channel_id STRING NOT NULL,
    channel_title STRING NOT NULL,
    custom_url STRING,
    uploads_playlist_id STRING,
    is_active BOOLEAN DEFAULT TRUE,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
    notes STRING
);

-- 3. Ежедневные снепшоты каналов (Партиционирование по дате)
CREATE TABLE IF NOT EXISTS `youtube_analytics.channel_snapshots` (
    channel_id STRING NOT NULL,
    channel_title STRING,
    snapshot_date DATE NOT NULL,
    subscriber_count INT64,
    total_views INT64,
    total_videos INT64,
    net_subscriber_growth INT64,
    net_view_growth INT64,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
)
PARTITION BY snapshot_date
CLUSTER BY channel_id;

-- 4. Снепшоты видеороликов (Партиционирование по дате замера)
CREATE TABLE IF NOT EXISTS `youtube_analytics.video_snapshots` (
    video_id STRING NOT NULL,
    channel_id STRING NOT NULL,
    channel_title STRING,
    title STRING,
    published_at TIMESTAMP,
    snapshot_timestamp TIMESTAMP NOT NULL,
    view_count INT64,
    like_count INT64,
    comment_count INT64,
    calculated_er FLOAT64,
    thumbnail_url STRING
)
PARTITION BY DATE(snapshot_timestamp)
CLUSTER BY channel_id, video_id;

-- 5. Представление (View) для мгновенного получения актуального среза по каналам
CREATE OR REPLACE VIEW `youtube_analytics.v_latest_channel_stats` AS
SELECT * EXCEPT(rn)
FROM (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY channel_id ORDER BY snapshot_date DESC) as rn
    FROM `youtube_analytics.channel_snapshots`
)
WHERE rn = 1;

-- 6. Представление (View) для топ-видео с наивысшей вовлеченностью (ER)
CREATE OR REPLACE VIEW `youtube_analytics.v_top_engaging_videos` AS
SELECT * EXCEPT(rn)
FROM (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY video_id ORDER BY snapshot_timestamp DESC) as rn
    FROM `youtube_analytics.video_snapshots`
)
WHERE rn = 1;
