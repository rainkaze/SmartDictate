from backend.app.services.text_processor import TextProcessor


def test_process_removes_fillers_and_adds_punctuation() -> None:
    processor = TextProcessor()

    result = processor.process("嗯 我 想 用 派森 开发 七牛 语音输入法", "general")

    assert result.text == "我，想，用，Python，开发，七牛云，语音输入法。"
    assert result.metrics.removed_fillers == 1


def test_process_adds_scene_prefix() -> None:
    processor = TextProcessor()

    result = processor.process("今天 讨论 项目 进度", "meeting")

    assert result.text.startswith("会议纪要：")
