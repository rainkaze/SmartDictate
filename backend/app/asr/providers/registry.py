from backend.app.asr.models import AsrProviderName
from backend.app.asr.providers.baidu import BaiduProvider
from backend.app.asr.providers.base import AsrProvider
from backend.app.asr.providers.mock import BrowserProvider, FutureProvider
from backend.app.asr.providers.xfyun import XfyunProvider
from backend.app.core.config import Settings


class AsrProviderRegistry:
    def __init__(self, settings: Settings) -> None:
        self._providers: dict[AsrProviderName, AsrProvider] = {
            AsrProviderName.BROWSER: BrowserProvider(),
            AsrProviderName.XFYUN_IAT: XfyunProvider(settings, AsrProviderName.XFYUN_IAT),
            AsrProviderName.XFYUN_LFASR_LARGE: XfyunProvider(
                settings,
                AsrProviderName.XFYUN_LFASR_LARGE,
            ),
            AsrProviderName.BAIDU_SHORT: BaiduProvider(settings, AsrProviderName.BAIDU_SHORT),
            AsrProviderName.BAIDU_REALTIME: BaiduProvider(
                settings,
                AsrProviderName.BAIDU_REALTIME,
            ),
            AsrProviderName.FUTURE: FutureProvider(),
        }

    def list(self) -> list[AsrProvider]:
        return list(self._providers.values())

    def get(self, provider: AsrProviderName) -> AsrProvider:
        return self._providers[provider]
