import pytest
from backend.app.asr.models import (
    AsrProviderName,
    AsrTranscriptionOptions,
    AudioLanguage,
    AudioSource,
    RecognitionMode,
)
from backend.app.asr.providers.registry import AsrProviderRegistry
from backend.app.asr.providers.xfyun import (
    _IatTranscriptAccumulator,
    _large_file_signature,
    _merge_incremental_text,
)
from backend.app.core.config import Settings


def test_asr_registry_exposes_extensible_provider_list() -> None:
    registry = AsrProviderRegistry(Settings())

    providers = {provider.info().id: provider.info() for provider in registry.list()}

    assert set(providers) == {
        AsrProviderName.BROWSER,
        AsrProviderName.XFYUN_IAT,
        AsrProviderName.XFYUN_LFASR_LARGE,
        AsrProviderName.FUTURE,
    }
    assert providers[AsrProviderName.BROWSER].enabled is True
    assert providers[AsrProviderName.XFYUN_IAT].enabled is False
    assert providers[AsrProviderName.XFYUN_IAT].supported_modes == [RecognitionMode.SHORT]
    assert providers[AsrProviderName.XFYUN_LFASR_LARGE].supported_modes == [RecognitionMode.LONG]
    assert AudioSource.SYSTEM in providers[AsrProviderName.XFYUN_LFASR_LARGE].supported_sources
    assert providers[AsrProviderName.XFYUN_LFASR_LARGE].enabled is False


def test_xfyun_provider_requires_credentials() -> None:
    registry = AsrProviderRegistry(Settings())

    with pytest.raises(RuntimeError, match="XFYUN_APP_ID"):
        registry.get(AsrProviderName.XFYUN_IAT).transcribe(
            Settings().database_file,
            AsrTranscriptionOptions(
                provider=AsrProviderName.XFYUN_IAT,
                source=AudioSource.FILE,
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
