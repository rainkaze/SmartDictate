import json
import shutil
from pathlib import Path
from uuid import uuid4

from backend.app.services.hotwords import HotwordDictionary
from backend.app.services.text_processor import TextProcessor
from backend.app.services.text_rules import load_text_rules

TEST_TMP_DIR = Path("backend/data/test-tmp-hotwords")


def create_dictionary() -> HotwordDictionary:
    TEST_TMP_DIR.mkdir(parents=True, exist_ok=True)
    return HotwordDictionary(data_file=str(TEST_TMP_DIR / f"{uuid4()}.json"))


def teardown_module() -> None:
    shutil.rmtree(TEST_TMP_DIR, ignore_errors=True)


def test_hotword_dictionary_lists_builtin_items() -> None:
    dictionary = create_dictionary()

    items = dictionary.list_items()

    assert any(item.source == "派森" and item.target == "Python" for item in items)
    assert all(item.builtin for item in items)


def test_hotword_dictionary_adds_custom_item() -> None:
    dictionary = create_dictionary()

    item = dictionary.add(" 小七 ", " 七牛云助手 ")

    assert item.source == "小七"
    assert item.target == "七牛云助手"
    assert item.builtin is False
    assert json.loads(dictionary.data_file.read_text(encoding="utf-8")) == {"小七": "七牛云助手"}


def test_hotword_dictionary_rejects_duplicate_item() -> None:
    dictionary = create_dictionary()

    try:
        dictionary.add("派森", "Python")
    except ValueError as exc:
        assert str(exc) == "热词已存在"
    else:
        raise AssertionError("重复热词应该被拒绝")


def test_hotword_dictionary_rejects_blank_item() -> None:
    dictionary = create_dictionary()

    try:
        dictionary.add("   ", " 七牛云助手 ")
    except ValueError as exc:
        assert str(exc) == "热词不能为空"
    else:
        raise AssertionError("空热词应该被拒绝")


def test_hotword_dictionary_deletes_custom_item() -> None:
    dictionary = create_dictionary()
    dictionary.add("小七", "七牛云助手")

    assert dictionary.delete("小七") is True
    assert dictionary.delete("派森") is False


def test_text_processor_uses_latest_custom_hotwords() -> None:
    dictionary = create_dictionary()
    processor = TextProcessor(rules_provider=dictionary.get_text_rules)

    dictionary.add("小七", "七牛云助手")
    result = processor.process("我 想 使用 小七 写 文档")

    assert result.text == "我，想，使用，七牛云助手，写，文档。"


def test_default_rules_are_valid_utf8() -> None:
    rules = load_text_rules()

    assert "嗯" in rules.filler_words
    assert rules.hotwords["七牛"] == "七牛云"
    assert rules.scene_prefixes["meeting"] == "会议纪要："
