"""
Exceptions for Surfa Ingest SDK
"""


class SurfaError(Exception):
    """Base exception for all Surfa SDK errors"""
    pass


class SurfaConfigError(SurfaError):
    """Raised when SDK configuration is invalid"""
    pass


class SurfaNetworkError(SurfaError):
    """Raised when network request fails"""
    pass


class SurfaValidationError(SurfaError):
    """Raised when event validation fails"""
    pass


class SurfaAuthError(SurfaError):
    """Raised when authentication fails (401/403)"""
    pass


class SurfaIngestError(SurfaError):
    """Raised when event ingestion fails (4xx/5xx)"""
    
    def __init__(self, message: str, status_code: int = None, response_text: str = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_text = response_text
