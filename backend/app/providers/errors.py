from __future__ import annotations


class ProviderError(Exception):
    def __init__(
        self,
        provider: str,
        message: str,
        *,
        status_code: int | None = None,
        retriable: bool = False,
    ) -> None:
        super().__init__(message)
        self.provider = provider
        self.status_code = status_code
        self.retriable = retriable


class ProviderConfigurationError(ProviderError):
    pass


class ProviderAuthenticationError(ProviderError):
    def __init__(self, provider: str, message: str, *, status_code: int | None = None) -> None:
        super().__init__(provider, message, status_code=status_code, retriable=False)


class ProviderRateLimitError(ProviderError):
    def __init__(self, provider: str, message: str, *, status_code: int | None = None) -> None:
        super().__init__(provider, message, status_code=status_code, retriable=True)


class ProviderTransportError(ProviderError):
    def __init__(self, provider: str, message: str, *, status_code: int | None = None) -> None:
        super().__init__(provider, message, status_code=status_code, retriable=True)


class ProviderUnavailableError(ProviderError):
    def __init__(self, provider: str, message: str, *, status_code: int | None = None) -> None:
        super().__init__(provider, message, status_code=status_code, retriable=True)


class ProviderPayloadError(ProviderError):
    pass
