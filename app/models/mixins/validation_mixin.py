# models/mixins/validation_mixin.py


class ValidationMixin:
    """
    Common validation hooks.

    Extend and override `validate` in concrete models
    (e.g., implement domain invariants).
    """

    def validate(self) -> None:
        """Raise exceptions if model state is invalid."""
        # No-op by default; override in subclasses.
        return