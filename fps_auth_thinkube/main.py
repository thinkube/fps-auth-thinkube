"""Asphalt component for Thinkube JupyterHub authentication."""

from asphalt.core import Component, Context
from jupyverse_api.app import App
from jupyverse_api.auth import Auth, AuthConfig

from .config import AuthThinkubeConfig
from .routes import auth_factory


class AuthThinkubeComponent(Component):
    """Asphalt component that provides Thinkube JupyterHub authentication."""

    def __init__(self, **kwargs):
        self.auth_thinkube_config = AuthThinkubeConfig(**kwargs)

    async def start(self, ctx: Context) -> None:
        """Start the component."""
        app = await ctx.request_resource(App)

        auth_thinkube = auth_factory(app, self.auth_thinkube_config)

        ctx.add_resource(auth_thinkube, types=[Auth])
        ctx.add_resource(self.auth_thinkube_config, types=[AuthConfig])
