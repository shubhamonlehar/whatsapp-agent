from typing import Any

from fastapi import HTTPException, status

from app.schemas import TrustSignalError, TrustSignalErrorResponse


def trustsignal_error(code: str, code_msg: str, message: str, http_status: int = 400) -> HTTPException:
    payload = TrustSignalErrorResponse(errors=[TrustSignalError(code=code, codeMsg=code_msg, message=message)])
    return HTTPException(status_code=http_status, detail=payload.model_dump())


def success_single(to: str, transaction_id: str) -> dict[str, Any]:
    return {
        "message": "Request process successfully",
        "results": {"to": to, "transaction_id": transaction_id},
        "success": True,
    }


def success_bulk(results: list[dict[str, Any]]) -> dict[str, Any]:
    return {"message": "Request process successfully", "results": results, "success": True}


def success_indicator() -> dict[str, Any]:
    return {"message": "", "success": True}


def validation_exception_handler_payload(exc: HTTPException) -> dict[str, Any]:
    if isinstance(exc.detail, dict) and "errors" in exc.detail:
        return exc.detail
    return TrustSignalErrorResponse(
        errors=[TrustSignalError(code="400", codeMsg="BAD_REQUEST", message=str(exc.detail))]
    ).model_dump()
