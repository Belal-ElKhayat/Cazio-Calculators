import json

from src.config import Config, normalize_hex
from src.themes import KEY_KINDS, Theme, build_custom_theme, build_qss, load_presets


def test_presets_load_and_cover_required_models():
    presets = load_presets()
    assert {"slate", "atomic_purple", "cyberpunk"} <= set(presets)
    assert presets["cyberpunk"].glow and presets["atomic_purple"].translucent


def test_custom_theme_and_qss():
    t = build_custom_theme("#223344", "#667788", "#a0c0a0")
    qss = build_qss(t)
    for kind in KEY_KINDS:
        assert f'QPushButton[kind="{kind}"]' in qss
    assert ":pressed" in qss and "border-bottom" in qss
    assert t.key_num == "#667788"


def test_theme_from_dict_ignores_bad_values():
    t = Theme.from_dict({"lcd_bg": "red", "body_top": "#123456", "nope": 1})
    assert t.lcd_bg == Theme().lcd_bg and t.body_top == "#123456"


def test_normalize_hex():
    assert normalize_hex("#ABC") == "#aabbcc"
    assert normalize_hex("12ab9f") == "#12ab9f"
    assert normalize_hex("#12") is None


def test_config_roundtrip_and_corruption(tmp_path):
    path = tmp_path / "config.json"
    cfg = Config(path)
    cfg.set_custom("#111111", "#222222", "#333333")
    cfg["arcade"]["highscores"]["snake"] = 7
    assert cfg.save()
    again = Config(path)
    assert again["custom"]["lcd"] == "#333333" and again["arcade"]["highscores"]["snake"] == 7
    path.write_text("{ not json", encoding="utf-8")
    broken = Config(path)
    assert broken["theme"] == "slate" and (tmp_path / "config.json.bak").exists()
    path.write_text(json.dumps({"custom": {"body": "nope"}, "angle": "xyz"}), encoding="utf-8")
    fixed = Config(path)
    assert fixed["custom"]["body"].startswith("#") and fixed["angle"] == "deg"
