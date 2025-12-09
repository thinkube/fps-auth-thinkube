"""User model for Thinkube authentication."""

from jupyverse_api.auth import User


class ThinkubeUser(User):
    """User model with all Jupyverse required fields."""

    # Core identity
    username: str = ""
    name: str = ""
    display_name: str = ""
    initials: str = ""
    avatar_url: str | None = None
    color: str | None = None

    # Session data (stored in-memory, not database)
    token: str = ""
    anonymous: bool = False
    workspace: str = "{}"
    settings: str = "{}"
    permissions: dict = {}

    class Config:
        # Allow creating from dict
        from_attributes = True
