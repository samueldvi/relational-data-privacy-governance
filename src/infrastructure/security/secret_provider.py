from __future__ import annotations

import os

from src.shared.errors import MaskingSecretError


class EnvironmentSecretProvider:
    def masking_secret(self) -> str:
        secret = os.environ.get("MASKING_SECRET")
        if not secret:
            raise MaskingSecretError("MASKING_SECRET is required.")
        return secret
