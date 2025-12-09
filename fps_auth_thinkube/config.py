"""Configuration for Thinkube JupyterHub authentication."""

from jupyverse_api.auth import AuthConfig
from pydantic import Field


class AuthThinkubeConfig(AuthConfig):
    """Thinkube JupyterHub authentication configuration.

    Most settings are auto-detected from JupyterHub environment variables.
    """

    cookie_name: str = Field(
        default="jupyverse_thinkube_token",
        description="Name of the session cookie"
    )
