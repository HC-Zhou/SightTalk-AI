"""Bailian application and compatible-model single-turn client."""

from __future__ import annotations

from typing import Any

import httpx

from sighttalk_api.core.config import Settings
from sighttalk_api.core.errors import AppError


class BailianApplicationClient:
    """Calls Bailian non-realtime completion APIs for debug fallback turns."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def complete(
        self,
        *,
        prompt: str,
        image_data_url: str | None = None,
        session_id: str | None = None,
    ) -> tuple[str, str | None]:
        """Run a prompt through the configured application or compatible API."""
        app_error: AppError | None = None
        app_id = self._settings.bailian_application_id
        if app_id:
            try:
                return await self._complete_with_application(
                    app_id=app_id,
                    prompt=prompt,
                    image_data_url=image_data_url,
                    session_id=session_id,
                )
            except AppError as exc:
                app_error = exc

        try:
            return await self._complete_with_compatible_api(
                prompt=prompt,
                image_data_url=image_data_url,
            )
        except AppError as exc:
            if app_error is not None:
                raise AppError(
                    exc.code,
                    f"{exc.message}; application fallback reason: {app_error.message}",
                    status_code=exc.status_code,
                ) from exc
            raise

    async def _complete_with_application(
        self,
        *,
        app_id: str,
        prompt: str,
        image_data_url: str | None,
        session_id: str | None,
    ) -> tuple[str, str | None]:
        """Call the Bailian application completion endpoint."""
        input_payload: dict[str, Any] = {"prompt": prompt}
        if session_id:
            input_payload["session_id"] = session_id
        if image_data_url:
            input_payload["image_list"] = [image_data_url]

        url = f"{self._settings.bailian_app_api_url.rstrip('/')}/apps/{app_id}/completion"
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {self._settings.bailian_api_key}",
                    "Content-Type": "application/json",
                },
                json={"input": input_payload, "parameters": {}, "debug": {}},
            )

        if response.status_code >= 400:
            raise AppError(
                "BAILIAN_REQUEST_FAILED",
                _error_message(response),
                status_code=502,
            )

        payload = response.json()
        output = payload.get("output", {})
        text = str(output.get("text") or "").strip()
        if not text:
            raise AppError("BAILIAN_EMPTY_RESPONSE", "Bailian returned an empty response", 502)
        return text, output.get("session_id")

    async def _complete_with_compatible_api(
        self,
        *,
        prompt: str,
        image_data_url: str | None,
    ) -> tuple[str, str | None]:
        """Call the OpenAI-compatible chat completion endpoint."""
        model = (
            self._settings.bailian_vision_model
            if image_data_url
            else self._settings.bailian_text_model
        )
        content: str | list[dict[str, Any]]
        if image_data_url:
            content = [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": image_data_url}},
            ]
        else:
            content = prompt

        url = f"{self._settings.bailian_compatible_api_url.rstrip('/')}/chat/completions"
        async with httpx.AsyncClient(timeout=45) as client:
            response = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {self._settings.bailian_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "你是 SightTalk AI，一个简洁准确的视觉语音助手。"
                                "如果用户提供了摄像头画面，请结合画面回答。"
                            ),
                        },
                        {"role": "user", "content": content},
                    ],
                    "max_tokens": 512,
                },
            )

        if response.status_code >= 400:
            raise AppError(
                "BAILIAN_REQUEST_FAILED",
                _error_message(response),
                status_code=502,
            )

        payload = response.json()
        choices = payload.get("choices", [])
        text = ""
        if choices:
            text = str(choices[0].get("message", {}).get("content") or "").strip()
        if not text:
            raise AppError("BAILIAN_EMPTY_RESPONSE", "Bailian returned an empty response", 502)
        return text, None


def _error_message(response: httpx.Response) -> str:
    """Extract a useful provider error message from a failed HTTP response."""
    try:
        payload = response.json()
    except ValueError:
        return response.text or f"Bailian request failed with status {response.status_code}"
    message = payload.get("message") or payload.get("error", {}).get("message")
    code = payload.get("code") or payload.get("error", {}).get("code")
    if code and message:
        return f"{code}: {message}"
    return str(message or payload)
