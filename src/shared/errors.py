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


class MaskingError(PrivacyGovernanceError):
    """Base error for deterministic masking rules."""


class MissingSecretError(MaskingError):
    pass


class WeakSecretError(MaskingError):
    pass


class InvalidConfigurationError(ConfigurationError, MaskingError):
    pass


class UnsupportedFormatError(MaskingError):
    pass


class ReviewRequiredError(MaskingError):
    pass


class PipelineExecutionError(PrivacyGovernanceError):
    pass


class ValidationError(PrivacyGovernanceError):
    pass


class UnresolvableCollisionError(MaskingError):
    pass


class UnsafeRepositoryError(PrivacyGovernanceError):
    pass


class SchemaDriftError(PrivacyGovernanceError):
    pass
