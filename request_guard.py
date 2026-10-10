"""Validate the ComfyUI prompt HTTP envelope before queueing work."""
import json
from aiohttp import web


@web.middleware
async def prompt_guard(request, handler):
    if request.method == "POST" and request.path in ("/prompt", "/api/prompt"):
        try:
            body = await request.json()
        except (json.JSONDecodeError, UnicodeDecodeError):
            return web.json_response({"error": "Request body must be valid JSON."}, status=400)
        if not isinstance(body, dict) or not isinstance(body.get("prompt"), dict) or not body["prompt"]:
            return web.json_response({"error": "Provide a nonempty prompt object containing workflow nodes."}, status=400)
        for node in body["prompt"].values():
            if not isinstance(node, dict) or not isinstance(node.get("class_type"), str) or not isinstance(node.get("inputs"), dict):
                return web.json_response({"error": "Each workflow node needs class_type and an inputs object."}, status=400)
    return await handler(request)


def install():
    from server import PromptServer
    app = PromptServer.instance.app
    if prompt_guard not in app.middlewares:
        app.middlewares.append(prompt_guard)
