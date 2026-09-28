class LiveProviderRequestNotAuthorizedError(RuntimeError):
    type = "live_provider_request_not_authorized"

    def __init__(self) -> None:
        super().__init__(self.type)
