from backend.app.services.text_processor import TextProcessor


def test_process_removes_fillers_and_adds_punctuation() -> None:
    processor = TextProcessor()

    result = processor.process("嗯 我 想 用 派森 开发 七牛 语音输入法", "general")

    assert result.text == "我想用 Python 开发七牛云语音输入法。"
    assert result.metrics.removed_fillers == 1


def test_process_does_not_add_scene_prefixes() -> None:
    processor = TextProcessor()

    result = processor.process("今天 讨论 项目 进度", "meeting")

    assert result.text == "今天讨论项目进度。"


def test_process_keeps_message_scene_as_plain_cleanup() -> None:
    processor = TextProcessor()

    result = processor.process("好的 我 稍后 发你 文档", "message")

    assert result.text == "好的我稍后发你文档。"


def test_process_keeps_existing_punctuation_readable() -> None:
    processor = TextProcessor()

    result = processor.process("今天完成前端联调，明天继续优化后端！", "general")

    assert result.text == "今天完成前端联调，明天继续优化后端！"


def test_process_applies_english_hotwords_case_insensitively() -> None:
    processor = TextProcessor()

    result = processor.process("github read me fast api", "code_note")

    assert result.text == "GitHub README FastAPI。"


def test_process_inserts_light_pause_before_connector_words() -> None:
    processor = TextProcessor()

    result = processor.process("我 想 使用 小七 写 文档 然后 复制 结果")

    assert result.text == "我想使用小七写文档，然后复制结果。"


def test_process_adds_spacing_around_latin_hotwords() -> None:
    processor = TextProcessor()

    result = processor.process("我想用派森开发七牛语音输入法")

    assert result.text == "我想用 Python 开发七牛云语音输入法。"


def test_process_cleans_compact_sample_text() -> None:
    processor = TextProcessor()

    result = processor.process("嗯我想用派森开发七牛语音输入法然后复制结果")

    assert result.text == "我想用 Python 开发七牛云语音输入法，然后复制结果。"
    assert result.metrics.removed_fillers == 1
