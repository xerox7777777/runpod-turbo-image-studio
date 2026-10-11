"""Keep the ComfyUI checkpoint folder browsable through Jupyter's Contents API."""
from jupyter_server.services.contents.handlers import ContentsHandler
from jupyter_server.utils import url_path_join


def _jupyter_server_extension_points():
    return [{'module': 'jupyter_workspace_routes'}]


def _load_jupyter_server_extension(serverapp):
    # Jupyter's generic .../checkpoints route otherwise interprets this directory
    # as a notebook checkpoint request and returns a list instead of a file model.
    # Reuse its authenticated ContentsHandler for this exact directory only;
    # notebook checkpoint APIs below it retain their normal behavior.
    pattern = url_path_join(serverapp.base_url, 'api/contents') + r'(?P<path>/ComfyUI/models/checkpoints)'
    serverapp.web_app.add_handlers('.*$', [(pattern, ContentsHandler)])
