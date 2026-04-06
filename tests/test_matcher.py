"""Tests for src/engine/matcher.py — answer matching from the answer bank."""

import pytest
from src.engine.matcher import match_answer, _resolve_dotpath, _clean, _is_inverted_phrasing, _try_skill_lookup, _find_skill


# ── _resolve_dotpath ──────────────────────────────────────────────────────

class TestResolveDotpath:
    def test_simple_key(self):
        assert _resolve_dotpath({"name": "Alice"}, "name") == "Alice"

    def test_nested_key(self):
        assert _resolve_dotpath({"a": {"b": "c"}}, "a.b") == "c"

    def test_array_index(self):
        data = {"items": [{"x": 1}, {"x": 2}]}
        assert _resolve_dotpath(data, "items[0].x") == 1
        assert _resolve_dotpath(data, "items[1].x") == 2

    def test_missing_key_returns_none(self):
        assert _resolve_dotpath({"a": 1}, "b") is None

    def test_array_out_of_bounds_returns_none(self):
        assert _resolve_dotpath({"items": []}, "items[0].x") is None

    def test_deep_nested(self):
        data = {"a": {"b": {"c": {"d": 42}}}}
        assert _resolve_dotpath(data, "a.b.c.d") == 42


# ── _clean ────────────────────────────────────────────────────────────────

class TestClean:
    def test_lowercase_strip(self):
        assert _clean("  HELLO World  ") == "hello world"

    def test_removes_punctuation(self):
        assert _clean("What's your email?") == "whats your email"


# ── _is_inverted_phrasing ─────────────────────────────────────────────────

class TestIsInvertedPhrasing:
    def test_without_sponsorship(self):
        entry = {"intent": "requires_sponsorship"}
        assert _is_inverted_phrasing("Can you work without sponsorship?", entry) is True

    def test_do_not_require(self):
        entry = {"intent": "requires_sponsorship"}
        assert _is_inverted_phrasing("I do not require sponsorship for employment", entry) is True

    def test_authorized_without(self):
        entry = {"intent": "requires_sponsorship"}
        assert _is_inverted_phrasing(
            "Are you authorized to work in the US without sponsorship?", entry
        ) is True

    def test_normal_phrasing_not_inverted(self):
        entry = {"intent": "requires_sponsorship"}
        assert _is_inverted_phrasing(
            "Do you require visa sponsorship?", entry
        ) is False

    def test_entry_specific_patterns(self):
        entry = {"inverted_phrasing": ["eligible without visa"]}
        assert _is_inverted_phrasing("Are you eligible without visa support?", entry) is True

    def test_empty_label(self):
        entry = {"intent": "requires_sponsorship"}
        assert _is_inverted_phrasing("", entry) is False


# ── match_answer ──────────────────────────────────────────────────────────

class TestMatchAnswer:
    def test_exact_intent_match(self, minimal_profile, minimal_answers):
        result = match_answer("work_authorization_us", minimal_profile, minimal_answers)
        assert result["answer"] == "Yes"
        assert result["source"] == "answers_bank"
        assert result["match_score"] == 1.0

    def test_profile_field_lookup(self, minimal_profile, minimal_answers):
        result = match_answer("first_name", minimal_profile, minimal_answers)
        assert result["answer"] == "Jacob"
        assert result["source"] == "profile"
        assert result["confidence"] == "high"

    def test_profile_email(self, minimal_profile, minimal_answers):
        result = match_answer("email", minimal_profile, minimal_answers)
        assert result["answer"] == "jacob@example.com"
        assert result["source"] == "profile"

    def test_profile_city(self, minimal_profile, minimal_answers):
        result = match_answer("city", minimal_profile, minimal_answers)
        assert result["answer"] == "Orlando"

    def test_no_match(self, minimal_profile, minimal_answers):
        result = match_answer("something_totally_unknown_xyz", minimal_profile, minimal_answers)
        assert result["confidence"] == "none"
        assert result["answer"] is None
        assert result["match_score"] == 0.0

    def test_inverted_phrasing_swaps_answer(self, minimal_profile, minimal_answers):
        result = match_answer(
            "requires_sponsorship",
            minimal_profile,
            minimal_answers,
            raw_label="Can you work in the US without sponsorship?",
        )
        assert result["answer"] == "Yes"  # inverted from "No"
        assert "inverted" in result["notes"].lower()

    def test_normal_phrasing_keeps_answer(self, minimal_profile, minimal_answers):
        result = match_answer(
            "requires_sponsorship",
            minimal_profile,
            minimal_answers,
            raw_label="Do you require visa sponsorship?",
        )
        assert result["answer"] == "No"  # normal answer

    def test_with_real_data(self, profile, answers):
        result = match_answer("salary_expectations", profile, answers)
        assert result["answer"] is not None
        assert result["source"] == "answers_bank"
        assert result["requires_review"] is True

    def test_fuzzy_cross_match(self, minimal_profile, minimal_answers):
        # "desired_salary" is not an exact intent match, but should fuzzy-match to salary_expectations
        result = match_answer("desired salary", minimal_profile, minimal_answers)
        # It should either fuzzy-match or return no match (depends on threshold)
        if result["source"] == "answers_bank":
            assert result["answer"] == "$110,000 - $120,000"


# ── _find_skill ───────────────────────────────────────────────────────────

class TestFindSkill:
    def test_exact_match(self):
        skill_map = {"python": {"name": "Python", "years": 3}}
        assert _find_skill("Python", skill_map)["name"] == "Python"

    def test_case_insensitive(self):
        skill_map = {"javascript": {"name": "JavaScript", "years": 3}}
        assert _find_skill("javascript", skill_map)["name"] == "JavaScript"

    def test_fuzzy_match(self):
        skill_map = {"node.js": {"name": "Node.js", "years": 2}}
        result = _find_skill("NodeJS", skill_map)
        assert result is not None
        assert result["name"] == "Node.js"

    def test_no_match(self):
        skill_map = {"python": {"name": "Python", "years": 3}}
        assert _find_skill("Haskell", skill_map) is None


# ── _try_skill_lookup ─────────────────────────────────────────────────────

class TestTrySkillLookup:
    def test_years_of_experience(self, minimal_profile):
        result = _try_skill_lookup("java_years", minimal_profile, "Years of Java experience")
        assert result is not None
        assert result["answer"] == "4"
        assert result["source"] == "profile"
        assert result["confidence"] == "high"

    def test_years_of_experience_alt_phrasing(self, minimal_profile):
        result = _try_skill_lookup("python_exp", minimal_profile, "How many years of experience with Python?")
        assert result is not None
        assert result["answer"] == "3"

    def test_years_unknown_skill(self, minimal_profile):
        result = _try_skill_lookup("rust_years", minimal_profile, "Years of Rust experience")
        assert result is None  # No match returns None to fall through

    def test_boolean_experience_yes(self, minimal_profile):
        result = _try_skill_lookup("java_exp", minimal_profile, "Do you have experience with Java?")
        assert result is not None
        assert result["answer"] == "Yes"
        assert result["confidence"] == "high"

    def test_boolean_experience_no(self, minimal_profile):
        result = _try_skill_lookup("go_exp", minimal_profile, "Do you have experience with Go?")
        assert result is not None
        assert result["answer"] is None
        assert result["confidence"] == "none"

    def test_boolean_proficient(self, minimal_profile):
        result = _try_skill_lookup("py_prof", minimal_profile, "Are you proficient in Python?")
        assert result is not None
        assert result["answer"] == "Yes"

    def test_no_pattern_match(self, minimal_profile):
        result = _try_skill_lookup("something", minimal_profile, "What is your favorite color?")
        assert result is None

    def test_empty_skills(self):
        profile = {"skills": []}
        result = _try_skill_lookup("java", profile, "Years of Java experience")
        assert result is None

    def test_via_match_answer(self, minimal_profile, minimal_answers):
        """Ensure _try_skill_lookup is reached through match_answer for an unknown intent."""
        result = match_answer(
            "unknown_skill_intent",
            minimal_profile,
            minimal_answers,
            raw_label="Do you have experience with JavaScript?",
        )
        assert result["answer"] == "Yes"
        assert result["source"] == "profile"
