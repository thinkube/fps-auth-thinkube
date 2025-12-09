"""Launch function for JupyterHub single-user server integration.

This module provides the launch() function that JupyterHub's
jupyterhub-singleuser script calls when JUPYTERHUB_SINGLEUSER_APP=jupyverse.
"""

import os
from urllib.parse import unquote, urlparse

from jupyverse_api.cli import main


def launch():
    """Launch Jupyverse as a JupyterHub single-user server.

    This function is called by jupyterhub-singleuser when
    JUPYTERHUB_SINGLEUSER_APP is set to 'jupyverse'.

    It configures Jupyverse with the correct base URL and mount path
    based on the JUPYTERHUB_SERVICE_URL environment variable.
    """
    service_url = unquote(os.environ.get("JUPYTERHUB_SERVICE_URL", ""))
    url = urlparse(service_url)
    return main.callback(
        open_browser=True,
        host=url.hostname,
        port=url.port,
        set_=(
            f"frontend.base_url={url.path}",
            f"app.mount_path={url.path}",
        ),
        disable=[],
    )
