# scripts/errors.py
class PipelineError(Exception):
    """Base exception for pipeline errors."""
    pass

class ValidationError(Exception):
    """Raised when validation fails."""
    pass
