from enum import Enum


class Service(str, Enum):
    GENERAL = "general"
    SUMO = "sumo"


class ServiceLayerException(Exception):
    def __init__(self, message: str, service: Service):
        super().__init__(f"{message} [service={service.value}]")
        self.message = message
        self.service = service

    def __str__(self) -> str:
        return f"{self.message} [service={self.service.value}]"


class InvalidDataError(ServiceLayerException):
    """Source data from the service is invalid or unexpected."""


class NoDataError(ServiceLayerException):
    """Expected data was not found."""


class ServiceRequestError(ServiceLayerException):
    """A request to an underlying service failed."""
