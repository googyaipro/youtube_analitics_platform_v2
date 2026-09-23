import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.core.database import Base
from backend.models.user import User
from backend.models.channel_set import ChannelSet
from backend.models.channel import Channel
from backend.models.video_metric import VideoMetric
from backend.services.analytics_service import AnalyticsService, parse_iso8601_duration


def test_parse_iso8601_duration():
    # Long formats
    secs, fmt = parse_iso8601_duration("PT1H2M30S")
    assert secs == 3750
    assert fmt == "1:02:30"

    secs, fmt = parse_iso8601_duration("PT15M42S")
    assert secs == 942
    assert fmt == "15:42"

    # Shorts formats (<= 60s)
    secs, fmt = parse_iso8601_duration("PT45S")
    assert secs == 45
    assert fmt == "0:45"
    assert 0 < secs <= 60

    secs, fmt = parse_iso8601_duration("PT1M")
    assert secs == 60
    assert fmt == "1:00"
    assert 0 < secs <= 60

    secs, fmt = parse_iso8601_duration("PT1M1S")
    assert secs == 61
    assert fmt == "1:01"
    assert secs > 60

    # Edge cases
    secs, fmt = parse_iso8601_duration("")
    assert secs == 0
    assert fmt == "--:--"

    secs, fmt = parse_iso8601_duration(None)
    assert secs == 0
    assert fmt == "--:--"


def test_analytics_service_enrichment_and_sorting():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine)
    db = TestingSession()

    user = User(
        email="analyst@test.com",
        hashed_password="hash",
        full_name="Analyst",
        language="ru"
    )
    db.add(user)
    db.commit()

    ch_set = ChannelSet(user_id=user.id, name="AI Rivals")
    db.add(ch_set)
    db.commit()

    ch1 = Channel(
        user_id=user.id,
        set_id=ch_set.id,
        channel_id="UC_CH1",
        title="AI Channel 1",
        subscriber_count=10000
    )
    db.add(ch1)
    db.commit()

    now = datetime.now(timezone.utc)

    # Long-form videos: 10,000, 20,000, 30,000 -> Median = 20,000
    v1 = VideoMetric(
        user_id=user.id, set_id=ch_set.id, video_id="vid_long_1",
        channel_id="UC_CH1", channel_title="AI Channel 1",
        title="Deep Dive Video 1", duration="PT10M0S",
        view_count=10000, like_count=500, comment_count=50,
        published_at=now - timedelta(days=2), extracted_at=now
    )
    v2 = VideoMetric(
        user_id=user.id, set_id=ch_set.id, video_id="vid_long_2",
        channel_id="UC_CH1", channel_title="AI Channel 1",
        title="Deep Dive Video 2", duration="PT15M0S",
        view_count=20000, like_count=1000, comment_count=100,
        published_at=now - timedelta(days=3), extracted_at=now
    )
    v3 = VideoMetric(
        user_id=user.id, set_id=ch_set.id, video_id="vid_long_3",
        channel_id="UC_CH1", channel_title="AI Channel 1",
        title="Viral Hit Video 3", duration="PT20M0S",
        view_count=60000, like_count=3000, comment_count=300,
        published_at=now - timedelta(days=1), extracted_at=now
    )

    # Shorts: 100,000, 200,000 -> Median = 150,000
    s1 = VideoMetric(
        user_id=user.id, set_id=ch_set.id, video_id="vid_short_1",
        channel_id="UC_CH1", channel_title="AI Channel 1",
        title="Short Tip 1", duration="PT30S",
        view_count=100000, like_count=5000, comment_count=200,
        published_at=now - timedelta(hours=5), extracted_at=now
    )
    s2 = VideoMetric(
        user_id=user.id, set_id=ch_set.id, video_id="vid_short_2",
        channel_id="UC_CH1", channel_title="AI Channel 1",
        title="Short Tip 2", duration="PT50S",
        view_count=200000, like_count=10000, comment_count=500,
        published_at=now - timedelta(hours=2), extracted_at=now
    )

    db.add_all([v1, v2, v3, s1, s2])
    db.commit()

    # 1. Test All Formats
    all_vids = AnalyticsService.get_set_enriched_videos(
        db, user.id, ch_set.id, limit=10, format_filter="all", sort_by="views"
    )
    assert len(all_vids) == 5
    assert all_vids[0]["video_id"] == "vid_short_2"  # 200,000 views

    # 2. Test Format Separation (Long-form only)
    long_vids = AnalyticsService.get_set_enriched_videos(
        db, user.id, ch_set.id, limit=10, format_filter="long", sort_by="views"
    )
    assert len(long_vids) == 3
    for v in long_vids:
        assert v["is_short"] is False
        assert v["format_type"] == "long"

    # Verify median for long-form:
    # Median of [10000, 20000, 60000] is 20000!
    # v3 has 60,000 views -> outlier_score should be 60000 / 20000 = 3.0x
    v3_enriched = next(v for v in long_vids if v["video_id"] == "vid_long_3")
    assert v3_enriched["channel_avg_views"] == 20000
    assert v3_enriched["outlier_score"] == 3.0
    assert any("Хит 3.0x" in b for b in v3_enriched["badges"])

    # 3. Test Format Separation (Shorts only)
    short_vids = AnalyticsService.get_set_enriched_videos(
        db, user.id, ch_set.id, limit=10, format_filter="short", sort_by="views"
    )
    assert len(short_vids) == 2
    for s in short_vids:
        assert s["is_short"] is True
        assert s["format_type"] == "short"

    # 4. Test Sorting by Outlier Score
    outlier_sorted = AnalyticsService.get_set_enriched_videos(
        db, user.id, ch_set.id, limit=10, format_filter="long", sort_by="outlier"
    )
    assert outlier_sorted[0]["video_id"] == "vid_long_3"  # Highest outlier (3.0x)

    # 5. Test Views to Subscribers Ratio
    # s2 has 200,000 views on a channel with 10,000 subs -> 2000% ratio!
    s2_enriched = next(v for v in all_vids if v["video_id"] == "vid_short_2")
    assert s2_enriched["views_to_subs_pct"] == 2000.0
    assert any("% к подп." in b for b in s2_enriched["badges"])

    db.close()
