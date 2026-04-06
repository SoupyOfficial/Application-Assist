"""Tests for src/detector/ — ATS platform detection from URLs."""

import pytest
from src.detector.platforms.greenhouse import matches_url as greenhouse_url
from src.detector.platforms.lever import matches_url as lever_url
from src.detector.platforms.ashby import matches_url as ashby_url
from src.detector.platforms.workday import matches_url as workday_url
from src.detector.detector import detect


# ── URL pattern matching ──────────────────────────────────────────────────

class TestGreenhouseURL:
    def test_boards_url(self):
        assert greenhouse_url("https://boards.greenhouse.io/company/jobs/12345") is True

    def test_job_boards_url(self):
        assert greenhouse_url("https://job-boards.greenhouse.io/company/jobs/12345") is True

    def test_subdomain(self):
        assert greenhouse_url("https://company.greenhouse.io/jobs/12345") is True

    def test_non_greenhouse(self):
        assert greenhouse_url("https://jobs.lever.co/company/12345") is False


class TestLeverURL:
    def test_lever_url(self):
        assert lever_url("https://jobs.lever.co/company/12345") is True

    def test_lever_subdomain(self):
        assert lever_url("https://jobs.lever.co/company") is True

    def test_non_lever(self):
        assert lever_url("https://boards.greenhouse.io/company") is False


class TestAshbyURL:
    def test_ashby_url(self):
        assert ashby_url("https://jobs.ashbyhq.com/company/12345") is True

    def test_non_ashby(self):
        assert ashby_url("https://example.com/jobs") is False


class TestWorkdayURL:
    def test_myworkdayjobs(self):
        assert workday_url("https://company.wd5.myworkdayjobs.com/en-US/External/job/12345") is True

    def test_workday_domain(self):
        assert workday_url("https://wd5.myworkday.com/company/recruiting") is True

    def test_non_workday(self):
        assert workday_url("https://jobs.lever.co/company") is False


# ── detect() orchestrator (URL-only, no page) ────────────────────────────

class TestDetectFromURL:
    def test_greenhouse(self):
        assert detect("https://boards.greenhouse.io/acme/jobs/1") == "greenhouse"

    def test_lever(self):
        assert detect("https://jobs.lever.co/acme/abc123") == "lever"

    def test_ashby(self):
        assert detect("https://jobs.ashbyhq.com/acme/abc") == "ashby"

    def test_workday(self):
        assert detect("https://acme.wd1.myworkdayjobs.com/External/job/x") == "workday"

    def test_unknown_falls_to_generic(self):
        assert detect("https://careers.example.com/apply/12345") == "generic"

    def test_empty_url(self):
        assert detect("") == "generic"
