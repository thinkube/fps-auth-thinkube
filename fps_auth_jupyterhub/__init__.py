"""Compatibility shim: fps_auth_jupyterhub -> fps_auth_thinkube.

JupyterHub's jupyterhub-singleuser script imports from fps_auth_jupyterhub,
so we provide this alias package that re-exports from fps_auth_thinkube.
"""

from fps_auth_thinkube import __version__, launch  # noqa: F401
