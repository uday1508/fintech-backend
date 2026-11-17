from typing import Any, Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ResponseMeta(BaseModel):
    request_id: str | None = None


class SuccessEnvelope(BaseModel, Generic[T]):
    data: T
    meta: ResponseMeta


class ErrorDetail(BaseModel):
    code: str
    message: str
    request_id: str | None = None


class ErrorEnvelope(BaseModel):
    error: ErrorDetail


def success_payload(data: Any, request_id: str | None = None) -> dict[str, Any]:
    return {"data": data, "meta": {"request_id": request_id}}
