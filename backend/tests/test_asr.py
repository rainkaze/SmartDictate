import pytest
from backend.app.asr.models import (
    AsrProviderName,
    AsrTranscriptionOptions,
    AudioLanguage,
    AudioSource,
    RecognitionMode,
)
from backend.app.asr.providers.baidu import (
    _BaiduRealtimeTranscriptAccumulator,
    _realtime_dev_pid,
    _short_dev_pid,
    validate_baidu_stream_request,
)
from backend.app.asr.providers.registry import AsrProviderRegistry
from backend.app.asr.providers.xfyun import (
    _IatTranscriptAccumulator,
    _large_file_signature,
    _merge_incremental_text,
)
from backend.app.asr.streaming import QueueAudioStream, validate_iat_stream_request
from backend.app.core.config import Settings


def test_asr_registry_exposes_extensible_provider_list() -> None:
    registry = AsrProviderRegistry(Settings())

    providers = {provider.info().id: provider.info() for provider in registry.list()}

    assert set(providers) == {
        AsrProviderName.BROWSER,
        AsrProviderName.XFYUN_IAT,
        AsrProviderName.XFYUN_LFASR_LARGE,
        AsrProviderName.BAIDU_SHORT,
        AsrProviderName.BAIDU_REALTIME,
        AsrProviderName.FUTURE,
    }
    assert providers[AsrProviderName.BROWSER].enabled is True
    assert providers[AsrProviderName.XFYUN_IAT].enabled is False
    assert providers[AsrProviderName.XFYUN_IAT].supported_modes == [RecognitionMode.REALTIME]
    assert AudioSource.FILE not in providers[AsrProviderName.XFYUN_IAT].supported_sources
    assert AudioLanguage.ZH_EN not in providers[AsrProviderName.XFYUN_IAT].supported_languages
    assert providers[AsrProviderName.XFYUN_LFASR_LARGE].supported_modes == [RecognitionMode.LONG]
    assert AudioSource.SYSTEM in providers[AsrProviderName.XFYUN_LFASR_LARGE].supported_sources
    assert providers[AsrProviderName.XFYUN_LFASR_LARGE].enabled is False
    assert providers[AsrProviderName.XFYUN_LFASR_LARGE].supported_languages == [
        AudioLanguage.ZH_CN,
        AudioLanguage.DIALECT,
    ]
    assert providers[AsrProviderName.BAIDU_SHORT].supported_modes == [RecognitionMode.SHORT]
    assert AudioSource.FILE in providers[AsrProviderName.BAIDU_SHORT].supported_sources
    assert AudioLanguage.ZH_EN not in providers[AsrProviderName.BAIDU_SHORT].supported_languages
    assert providers[AsrProviderName.BAIDU_REALTIME].supported_modes == [RecognitionMode.REALTIME]
    assert AudioSource.FILE not in providers[AsrProviderName.BAIDU_REALTIME].supported_sources
    assert providers[AsrProviderName.BAIDU_SHORT].enabled is False


def test_xfyun_provider_requires_credentials() -> None:
    registry = AsrProviderRegistry(Settings())

    with pytest.raises(RuntimeError, match="XFYUN_APP_ID"):
        registry.get(AsrProviderName.XFYUN_IAT).transcribe(
            Settings().database_file,
            AsrTranscriptionOptions(
                provider=AsrProviderName.XFYUN_IAT,
                source=AudioSource.MICROPHONE,
                language=AudioLanguage.ZH_EN,
                mode=RecognitionMode.SHORT,
            ),
        )


def test_xfyun_provider_configuration_is_isolated_by_interface() -> None:
    registry = AsrProviderRegistry(
        Settings(
            xfyun_app_id="app",
            xfyun_api_key="iat-key",
            xfyun_api_secret="iat-secret",
        )
    )

    providers = {provider.info().id: provider.info() for provider in registry.list()}

    assert providers[AsrProviderName.XFYUN_IAT].enabled is True
    assert providers[AsrProviderName.XFYUN_LFASR_LARGE].enabled is True


def test_baidu_provider_configuration_exposes_short_and_realtime() -> None:
    registry = AsrProviderRegistry(
        Settings(
            baidu_asr_app_id="123",
            baidu_asr_api_key="api-key",
            baidu_asr_secret_key="secret-key",
        )
    )

    providers = {provider.info().id: provider.info() for provider in registry.list()}

    assert providers[AsrProviderName.BAIDU_SHORT].enabled is True
    assert providers[AsrProviderName.BAIDU_REALTIME].enabled is True


def test_baidu_realtime_rejects_local_file_source() -> None:
    with pytest.raises(ValueError, match="不支持本机文件上传"):
        validate_baidu_stream_request(
            Settings(
                baidu_asr_app_id="123",
                baidu_asr_api_key="api-key",
                baidu_asr_secret_key="secret-key",
            ),
            AudioSource.FILE,
        )


def test_baidu_model_pid_mapping_matches_supported_languages() -> None:
    assert _short_dev_pid(AudioLanguage.ZH_CN) == 1537
    assert _short_dev_pid(AudioLanguage.EN_US) == 1737
    assert _short_dev_pid(AudioLanguage.DIALECT) == 1637
    assert _realtime_dev_pid(AudioLanguage.ZH_CN) == 15372
    assert _realtime_dev_pid(AudioLanguage.EN_US) == 17372
    assert _realtime_dev_pid(AudioLanguage.DIALECT) == 15376


def test_baidu_realtime_accumulator_replaces_sentence_partials() -> None:
    accumulator = _BaiduRealtimeTranscriptAccumulator()

    assert accumulator.update_partial("北京天气怎") == "北京天气怎"
    assert accumulator.update_partial("北京天气怎么样") == "北京天气怎么样"
    assert accumulator.add_final("北京天气怎么样。") == "北京天气怎么样。"
    assert accumulator.update_partial("上海") == "北京天气怎么样。上海"


def test_iat_rejects_local_file_upload() -> None:
    registry = AsrProviderRegistry(
        Settings(
            xfyun_app_id="app",
            xfyun_api_key="iat-key",
            xfyun_api_secret="iat-secret",
        )
    )

    with pytest.raises(RuntimeError, match="不支持本机文件上传"):
        registry.get(AsrProviderName.XFYUN_IAT).transcribe(
            Settings().database_file,
            AsrTranscriptionOptions(
                provider=AsrProviderName.XFYUN_IAT,
                source=AudioSource.FILE,
                language=AudioLanguage.ZH_EN,
                mode=RecognitionMode.SHORT,
            ),
        )


def test_iat_stream_request_rejects_local_file_source() -> None:
    with pytest.raises(ValueError, match="不支持本机文件上传"):
        validate_iat_stream_request(
            Settings(
                xfyun_app_id="app",
                xfyun_api_key="iat-key",
                xfyun_api_secret="iat-secret",
            ),
            AudioSource.FILE,
        )


def test_queue_audio_stream_reads_buffered_chunks() -> None:
    stream = QueueAudioStream()
    stream.write(b"abcdef")
    stream.close()

    assert stream.read(2) == b"ab"
    assert stream.read(3) == b"cde"
    assert stream.read(3) == b"f"
    assert stream.read(3) == b""


def test_large_file_signature_is_stable_for_sorted_params() -> None:
    signature = _large_file_signature(
        {
            "fileName": "sample.wav",
            "accessKeyId": "key",
            "dateTime": "2026-05-24T16:00:00+0800",
        },
        "secret",
    )

    assert signature == "3KnFxnSiHOOY/welaG++nLb8uOc="


def test_merge_incremental_text_keeps_final_iat_hypothesis() -> None:
    transcript = ""
    for chunk in ["语", "语音", "语音听", "语音听写", "语音听写可以"]:
        transcript = _merge_incremental_text(transcript, chunk)

    assert transcript == "语音听写可以"


def test_merge_incremental_text_appends_non_overlapping_text() -> None:
    transcript = _merge_incremental_text("语音听写可以", "将语音转换为文字。")

    assert transcript == "语音听写可以将语音转换为文字。"


def test_iat_accumulator_replaces_dynamic_corrections() -> None:
    accumulator = _IatTranscriptAccumulator()

    accumulator.update({"result": {"pgs": "apd", "rg": [1, 1]}}, "语音听写")
    accumulator.update({"result": {"pgs": "apd", "rg": [2, 2]}}, "可以")
    accumulator.update({"result": {"pgs": "rpl", "rg": [2, 2]}}, "可以将语音转换为文字。")

    assert accumulator.text == "语音听写可以将语音转换为文字。"


def test_iat_accumulator_replaces_progressive_apd_fragments() -> None:
    accumulator = _IatTranscriptAccumulator()

    accumulator.update({"result": {"pgs": "apd"}}, "说来")
    accumulator.update({"result": {"pgs": "apd"}}, "说来君子")
    accumulator.update({"result": {"pgs": "apd"}}, "说来君子见")
    accumulator.update({"result": {"pgs": "apd"}}, "说来君子见已达人之命")
    accumulator.update({"result": {"pgs": "apd"}}, "老当益壮")

    assert accumulator.text == "说来君子见已达人之命老当益壮"


def test_iat_accumulator_uses_sentence_numbers_for_streaming_updates() -> None:
    accumulator = _IatTranscriptAccumulator()

    accumulator.update({"result": {"sn": 1, "pgs": "apd"}}, "下临无地")
    accumulator.update({"result": {"sn": 1, "pgs": "apd"}}, "下临无地可行")
    accumulator.update({"result": {"sn": 2, "pgs": "apd"}}, "穷岛屿之萦回")

    assert accumulator.text == "下临无地可行穷岛屿之萦回"


def test_iat_accumulator_replaces_numbered_sentence_range() -> None:
    accumulator = _IatTranscriptAccumulator()

    accumulator.update({"result": {"sn": 1, "pgs": "apd"}}, "下临无地")
    accumulator.update({"result": {"sn": 2, "pgs": "apd"}}, "可行可行")
    accumulator.update({"result": {"sn": 3, "pgs": "rpl", "rg": [2, 2]}}, "可极娱游")

    assert accumulator.text == "下临无地可极娱游"
