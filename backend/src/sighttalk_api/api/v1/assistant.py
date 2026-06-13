from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from sighttalk_api.core.config import Settings, get_settings
from sighttalk_api.core.errors import AppError
from sighttalk_api.schemas.assistant import AssistantTurnRequest, AssistantTurnResponse
from sighttalk_api.services.bailian_application import BailianApplicationClient

router = APIRouter(prefix="/assistant", tags=["assistant"])


@router.post("/turn")
async def create_assistant_turn(
    request: AssistantTurnRequest,
    settings: Annotated[Settings, Depends(get_settings)],
) -> AssistantTurnResponse:
    if settings.ai_provider != "bailian":
        raise AppError("PROVIDER_DISABLED", "Assistant turn endpoint requires AI_PROVIDER=bailian")
    try:
        settings.validate_for_session()
    except ValueError as exc:
        raise AppError("CONFIGURATION_ERROR", str(exc), status_code=500) from exc

    client = BailianApplicationClient(settings)
    text, session_id = await client.complete(
        prompt=request.prompt,
        image_data_url=request.image_data_url,
        session_id=request.bailian_session_id,
    )
    return AssistantTurnResponse(
        room_name=request.room_name,
        text=text,
        bailian_session_id=session_id,
    )
