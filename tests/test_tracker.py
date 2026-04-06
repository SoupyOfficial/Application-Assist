"""Tests for src/tracker/db.py — SQLite application tracking."""

import os
import pytest
from unittest.mock import patch
from src.tracker import db as tracker_db


class TestTracker:
    @pytest.fixture(autouse=True)
    def setup_db(self, tmp_path):
        """Patch DB_PATH to a temp file and init the database."""
        self.db_path = str(tmp_path / "test_applications.db")
        self._patcher = patch.object(tracker_db, "DB_PATH", self.db_path)
        self._patcher.start()
        tracker_db.init_db()

    def teardown_method(self):
        self._patcher.stop()

    def test_init_creates_db(self):
        assert os.path.exists(self.db_path)

    def test_log_and_retrieve(self):
        tracker_db.log_application(
            company="Acme Corp",
            role="Software Engineer",
            url="https://boards.greenhouse.io/acme/jobs/1",
            ats_platform="greenhouse",
            mode="fill_and_pause",
            status="completed",
            time_saved_seconds=120,
        )
        stats = tracker_db.get_stats()
        assert stats["total_applications"] == 1
        assert stats["by_platform"].get("greenhouse", 0) == 1

    def test_multiple_applications(self):
        for i, platform in enumerate(["greenhouse", "lever", "greenhouse"]):
            tracker_db.log_application(
                company=f"Company {i}",
                role="Engineer",
                url=f"https://example.com/{i}",
                ats_platform=platform,
                mode="fill_only",
                status="completed",
                time_saved_seconds=60,
            )
        stats = tracker_db.get_stats()
        assert stats["total_applications"] == 3
        assert stats["by_platform"].get("greenhouse", 0) == 2
        assert stats["by_platform"].get("lever", 0) == 1

    def test_get_history(self):
        tracker_db.log_application(url="https://example.com/1", company="A", status="filled")
        tracker_db.log_application(url="https://example.com/2", company="B", status="submitted")
        history = tracker_db.get_history(limit=10)
        assert len(history) == 2
        # Most recent first
        assert history[0]["company"] == "B"
