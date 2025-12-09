"""FastAPI routes for Thinkube JupyterHub authentication.

This is a simplified version of fps-auth-jupyterhub that:
- Uses in-memory user storage instead of SQLAlchemy
- No async database issues (MissingGreenlet errors)
- Cleaner, more maintainable code
"""

import json
import os
from collections.abc import Awaitable, Callable
from datetime import datetime
from functools import partial
from typing import Annotated, Any

from anyio import TASK_STATUS_IGNORED, Lock, create_task_group, sleep
from anyio.abc import TaskStatus
from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, WebSocket, status
from fastapi.responses import RedirectResponse
from httpx import AsyncClient
from jupyterhub.services.auth import HubOAuth
from jupyterhub.utils import isoformat
from jupyverse_api import Router
from jupyverse_api.app import App
from jupyverse_api.auth import Auth, User

from .config import AuthThinkubeConfig
from .models import ThinkubeUser


def auth_factory(
    app: App,
    auth_thinkube_config: AuthThinkubeConfig,
):
    """Factory function to create the auth plugin."""

    class AuthThinkube(Auth, Router):
        """Thinkube JupyterHub authentication implementation for Jupyverse.

        Key differences from fps-auth-jupyterhub:
        - Uses in-memory dict for user storage (no SQLAlchemy)
        - Thread-safe with Lock
        - No MissingGreenlet errors
        """

        def __init__(self) -> None:
            super().__init__(app)

            # In-memory user storage: token -> ThinkubeUser
            self._users: dict[str, ThinkubeUser] = {}
            self._lock = Lock()

            # JupyterHub integration
            self.hub_auth = HubOAuth()
            self.http_client = AsyncClient()

            # Environment variables set by JupyterHub
            self.activity_url = os.environ.get("JUPYTERHUB_ACTIVITY_URL")
            self.server_name = os.environ.get("JUPYTERHUB_SERVER_NAME")

            # Cookie name
            self.cookie_name = auth_thinkube_config.cookie_name

            router = APIRouter()

            @router.get("/oauth_callback")
            async def oauth_callback(
                request: Request,
                code: str | None = None,
                state: str | None = None,
            ):
                """Handle OAuth callback from JupyterHub."""
                if code is None:
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

                # Validate state
                cookie_state = request.cookies.get(self.hub_auth.state_cookie_name)
                if state is None or state != cookie_state:
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

                # Exchange code for token
                token = self.hub_auth.token_for_code(code)

                # Get user info from JupyterHub
                hub_user = await self.hub_auth.user_for_token(token, use_cache=False, sync=False)

                if hub_user is None:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Failed to get user info from JupyterHub"
                    )

                # Create user object
                username = hub_user.get("name", "anonymous")
                display_name = hub_user.get("name", username)
                initials = "".join(word[0].upper() for word in display_name.split() if word)

                user = ThinkubeUser(
                    token=token,
                    username=username,
                    name=username,
                    display_name=display_name,
                    initials=initials or username[0].upper(),
                    anonymous=False,
                )

                # Store user in memory
                async with self._lock:
                    self._users[token] = user

                # Redirect to original URL
                next_url = self.hub_auth.get_next_url(cookie_state)
                response = RedirectResponse(next_url)
                response.set_cookie(key=self.cookie_name, value=token)
                return response

            @router.get("/api/me")
            async def get_api_me(
                request: Request,
                user: User = Depends(self.current_user()),
            ):
                """Get current user information."""
                checked_permissions: dict[str, list[str]] = {}
                permissions = json.loads(
                    dict(request.query_params).get("permissions", "{}").replace("'", '"')
                )
                if permissions:
                    user_permissions: dict[str, list[str]] = {}
                    for resource, actions in permissions.items():
                        user_resource_permissions = user_permissions.get(resource, [])
                        allowed = checked_permissions[resource] = []
                        for action in actions:
                            if action in user_resource_permissions:
                                allowed.append(action)

                keys = ["username", "name", "display_name", "initials", "avatar_url", "color"]
                identity = {k: getattr(user, k, None) for k in keys}
                return {
                    "identity": identity,
                    "permissions": checked_permissions,
                }

            self.include_router(router)

        def current_user(self, permissions: dict[str, list[str]] | None = None) -> Callable:
            """Get dependency for current user."""

            async def _(
                request: Request,
                token: Annotated[str | None, Cookie(alias=self.cookie_name)] = None,
            ) -> ThinkubeUser:
                if token is not None:
                    # Validate token with JupyterHub
                    hub_user = await self.hub_auth.user_for_token(
                        token, use_cache=False, sync=False
                    )

                    if hub_user is None:
                        # Token invalid, redirect to login
                        raise self._redirect_to_login(request)

                    # Check scopes
                    scopes = self.hub_auth.check_scopes(self.hub_auth.access_scopes, hub_user)
                    if not scopes:
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail=f"User {hub_user['name']} cannot access this server",
                        )

                    # Get or create user from memory
                    async with self._lock:
                        user = self._users.get(token)
                        if user is None:
                            # Create user if not in memory (e.g., after restart)
                            username = hub_user.get("name", "anonymous")
                            display_name = hub_user.get("name", username)
                            initials = "".join(word[0].upper() for word in display_name.split() if word)

                            user = ThinkubeUser(
                                token=token,
                                username=username,
                                name=username,
                                display_name=display_name,
                                initials=initials or username[0].upper(),
                                anonymous=False,
                            )
                            self._users[token] = user

                    # Report activity to JupyterHub
                    if self.activity_url:
                        headers = {
                            "Authorization": f"token {self.hub_auth.api_token}",
                            "Content-Type": "application/json",
                        }
                        last_activity = isoformat(datetime.utcnow())
                        self.task_group.start_soon(
                            partial(
                                self.http_client.post,
                                self.activity_url,
                                headers=headers,
                                json={
                                    "servers": {self.server_name: {"last_activity": last_activity}}
                                },
                            )
                        )

                    return user

                # No token - check if permissions required
                if permissions:
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

                # Redirect to JupyterHub login
                raise self._redirect_to_login(request)

            return _

        def _redirect_to_login(self, request: Request) -> HTTPException:
            """Create redirect to JupyterHub login."""
            state = self.hub_auth.generate_state(next_url=str(request.url))
            return HTTPException(
                status_code=status.HTTP_307_TEMPORARY_REDIRECT,
                headers={
                    "Location": f"{self.hub_auth.login_url}&state={state}",
                    "Set-Cookie": f"{self.hub_auth.state_cookie_name}={state}",
                },
            )

        async def update_user(
            self, token: Annotated[str | None, Cookie(alias="jupyverse_thinkube_token")] = None
        ) -> Callable:
            """Get dependency for updating user."""

            async def _(data: dict[str, Any]) -> ThinkubeUser | None:
                if token is not None:
                    async with self._lock:
                        user = self._users.get(token)
                        if user:
                            # Update user fields
                            for k, v in data.items():
                                if hasattr(user, k):
                                    setattr(user, k, v)
                            return user
                return None

            return _

        def websocket_auth(
            self,
            permissions: dict[str, list[str]] | None = None,
        ) -> Callable[[Any], Awaitable[tuple[Any, dict[str, list[str]] | None] | None]]:
            """Get dependency for WebSocket authentication."""

            async def _(
                websocket: WebSocket,
            ) -> tuple[Any, dict[str, list[str]] | None] | None:
                accept_websocket = False

                if self.cookie_name in websocket._cookies:
                    token = websocket._cookies[self.cookie_name]

                    # Validate token with JupyterHub
                    hub_user = await self.hub_auth.user_for_token(
                        token, use_cache=False, sync=False
                    )

                    if hub_user is not None:
                        accept_websocket = True

                if accept_websocket:
                    return websocket, permissions
                else:
                    await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                    return None

            return _

        async def start(self, *, task_status: TaskStatus[None] = TASK_STATUS_IGNORED) -> None:
            """Start the auth plugin."""
            async with create_task_group() as tg:
                self.task_group = tg
                task_status.started()
                await sleep(float("inf"))

        async def stop(self) -> None:
            """Stop the auth plugin."""
            await self.http_client.aclose()
            self.task_group.cancel_scope.cancel()

    return AuthThinkube()
