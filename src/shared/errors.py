"""Safe, specific exception hierarchy for application boundaries."""


class PrivacyGovernanceError(Exception):
    """Base class for errors safe to translate at the CLI boundary."""


class ConfigurationError(PrivacyGovernanceError):
    pass


class DatabaseUnavailableError(PrivacyGovernanceError):
    pass


class RegistryValidationError(PrivacyGovernanceError):
    pass


class MaskingSecretError(PrivacyGovernanceError):
    pass


class PipelineExecutionError(PrivacyGovernanceError):
    pass


class ValidationError(PrivacyGovernanceError):
    pass


class UnresolvableCollisionError(PrivacyGovernanceError):
    pass


class UnsafeRepositoryError(PrivacyGovernanceError):
    pass
