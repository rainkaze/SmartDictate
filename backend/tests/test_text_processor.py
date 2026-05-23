from backend.app.services.text_processor import TextProcessor


def test_process_removes_fillers_and_adds_punctuation() -> None:
    processor = TextProcessor()

    result = processor.process("嗯 我 想 用 派森 开发 七牛 语音输入法", "general")

    assert result.text == "我，想，用，Python，开发，七牛云，语音输入法。"
    assert result.metrics.removed_fillers == 1


def test_process_applies_scene_prefix() -> None:
    processor = TextProcessor()

    result = processor.process("今天 讨论 项目 进度", "meeting")

    assert result.text == "会议纪要：今天，讨论，项目，进度。"


def test_process_keeps_existing_punctuation_readable() -> None:
    processor = TextProcessor()

    result = processor.process("今天完成前端联调，明天继续优化后端！", "general")

    assert result.text == "今天完成前端联调，明天继续优化后端！"


def test_process_applies_english_hotwords_case_insensitively() -> None:
    processor = TextProcessor()

    result = processor.process("github read me fast api", "code_note")

    assert result.text == "代码说明：GitHub，README，FastAPI。"
