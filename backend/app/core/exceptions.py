from fastapi import HTTPException


class ExtractionError(HTTPException):
    def __init__(self, detail: str = "Failed to extract content from URL"):
        super().__init__(status_code=422, detail=detail)


class PlaceResolutionError(HTTPException):
    def __init__(self, detail: str = "Failed to resolve place"):
        super().__init__(status_code=422, detail=detail)


class TripGenerationError(HTTPException):
    def __init__(self, detail: str = "Failed to generate trip plan"):
        super().__init__(status_code=500, detail=detail)


class APIKeyMissingError(HTTPException):
    def __init__(self, service: str):
        super().__init__(
            status_code=500,
            detail=f"API key for {service} is not configured",
        )
