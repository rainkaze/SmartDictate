import json
import shutil
from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import pytest
from backend.app.services.hotwords import HotwordDictionary
from backend.app.services.text_processor import TextProcessor
from backend.app.services.text_rules import load_text_rules

TEST_RUNTIME_DIR = Path("backend/data/test-runtime/hotwords")


@pytest.fixture()
def hotword_dir() -> Iterator[Path]:
    test_dir = TEST_RUNTIME_DIR / uuid4().hex
    test_dir.mkdir(parents=True, exist_ok=True)
    try:
        yield test_dir
    finally:
        shutil.rmtree(test_dir, ignore_errors=True)


def create_dictionary(hotword_dir: Path) -> HotwordDictionary:
    return HotwordDictionary(data_file=str(hotword_dir / f"{uuid4()}.json"))


def test_hotword_dictionary_lists_builtin_items(hotword_dir: Path) -> None:
    dictionary = create_dictionary(hotword_dir)

    items = dictionary.list_items()

    assert any(item.source == "派森" and item.target == "Python" for item in items)
    assert all(item.builtin for item in items)


def test_hotword_dictionary_adds_custom_item(hotword_dir: Path) -> None:
    dictionary = create_dictionary(hotword_dir)

    item = dictionary.add(" 小七 ", " 七牛云助手 ")

    assert item.source == "小七"
    assert item.target == "七牛云助手"
    assert item.builtin is False
    assert json.loads(dictionary.data_file.read_text(encoding="utf-8")) == {"小七": "七牛云助手"}


def test_hotword_dictionary_rejects_duplicate_item(hotword_dir: Path) -> None:
    dictionary = create_dictionary(hotword_dir)

    try:
        dictionary.add("派森", "Python")
    except ValueError as exc:
        assert str(exc) == "热词已存在"
    else:
        raise AssertionError("重复热词应该被拒绝")


def test_hotword_dictionary_rejects_blank_item(hotword_dir: Path) -> None:
    dictionary = create_dictionary(hotword_dir)

    try:
        dictionary.add("   ", " 七牛云助手 ")
    except ValueError as exc:
        assert str(exc) == "热词不能为空"
    else:
        raise AssertionError("空热词应该被拒绝")


def test_hotword_dictionary_deletes_custom_item(hotword_dir: Path) -> None:
    dictionary = create_dictionary(hotword_dir)
    dictionary.add("小七", "七牛云助手")

    assert dictionary.delete("小七") is True
    assert dictionary.delete("派森") is False


def test_text_processor_uses_latest_custom_hotwords(hotword_dir: Path) -> None:
    dictionary = create_dictionary(hotword_dir)
    processor = TextProcessor(rules_provider=dictionary.get_text_rules)

    dictionary.add("小七", "七牛云助手")
    result = processor.process("我 想 使用 小七 写 文档")

    assert result.text == "我想使用七牛云助手写文档。"


def test_default_rules_are_valid_utf8() -> None:
    rules = load_text_rules()

    assert "嗯" in rules.filler_words
    assert rules.hotwords["七牛"] == "七牛云"
    assert rules.scene_prefixes["meeting"] == "会议纪要："
