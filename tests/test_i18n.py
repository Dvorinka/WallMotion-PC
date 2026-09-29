"""Tests for locales/*.json and wallmotion.i18n loading."""

import json
from pathlib import Path

import wallmotion.i18n as i18n

LOCALES_DIR = Path(i18n.__file__).resolve().parent.parent / "locales"


class TestLocaleFiles:
    def test_files_exist(self):
        assert (LOCALES_DIR / "cs.json").is_file()
        assert (LOCALES_DIR / "en.json").is_file()

    def test_valid_json(self):
        for lang in ("cs", "en"):
            text = (LOCALES_DIR / f"{lang}.json").read_text(encoding="utf-8")
            assert isinstance(json.loads(text), dict)

    def test_same_keys(self):
        cs = json.loads((LOCALES_DIR / "cs.json").read_text(encoding="utf-8"))
        en = json.loads((LOCALES_DIR / "en.json").read_text(encoding="utf-8"))
        assert sorted(cs) == sorted(en)
        assert len(cs) > 0

    def test_no_empty_values(self):
        for lang in ("cs", "en"):
            data = json.loads((LOCALES_DIR / f"{lang}.json").read_text(encoding="utf-8"))
            for key, value in data.items():
                assert isinstance(value, str) and value.strip(), (lang, key)

    def test_strings_match_files(self):
        for lang in ("cs", "en"):
            data = json.loads((LOCALES_DIR / f"{lang}.json").read_text(encoding="utf-8"))
            assert i18n.STRINGS[lang] == data

    def test_format_placeholders_preserved(self):
        # e.g. "screen_one": "Obrazovka: {w} × {h}" must still format.
        for lang in ("cs", "en"):
            s = i18n.STRINGS[lang]
            assert "{w}" in s["screen_one"] and "{h}" in s["screen_one"]
            s["screen_one"].format(w=1920, h=1080)
            s["yt_downloading"].format(p="42%")
