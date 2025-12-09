# fps-auth-thinkube

A Jupyverse authentication plugin for JupyterHub - simplified and reliable.

This is a clean rewrite of `fps-auth-jupyterhub` that eliminates the SQLAlchemy async issues (MissingGreenlet errors) by using in-memory user storage instead.

## Why This Exists

The official `fps-auth-jupyterhub` plugin has chronic issues with SQLAlchemy's async session management, causing `MissingGreenlet` errors when accessing user attributes outside the async context. This plugin solves that by:

1. **No SQLAlchemy** - Uses simple in-memory dict for user storage
2. **Thread-safe** - Uses anyio Lock for concurrent access
3. **Simpler code** - Easier to understand and maintain
4. **Same functionality** - Full JupyterHub OAuth integration

## Installation

```bash
pip install fps-auth-thinkube
```

Or install from source:

```bash
pip install git+https://github.com/thinkube/fps-auth-thinkube.git
```

## Requirements

- JupyterHub 5.0+
- Jupyverse 0.6.0+
- Must be run as a JupyterHub single-user server

## Usage

### JupyterHub Configuration

In your JupyterHub config, set the single-user app to Jupyverse:

```python
c.KubeSpawner.environment = {
    'JUPYTERHUB_SINGLEUSER_APP': 'jupyverse'
}
```

### Container Image

Your Jupyter container image should have:

```dockerfile
RUN pip install \
    "jupyverse[jupyterlab]>=0.10.0" \
    "jupyterhub>=5.0.0" \
    fps-auth-thinkube
```

### Running Jupyverse

When JupyterHub spawns the server, it sets environment variables that `fps-auth-thinkube` uses automatically:

- `JUPYTERHUB_API_TOKEN` - API token for JupyterHub
- `JUPYTERHUB_API_URL` - JupyterHub API URL
- `JUPYTERHUB_ACTIVITY_URL` - URL to report activity
- `JUPYTERHUB_SERVER_NAME` - Server name for activity reporting

Jupyverse should be started with:

```bash
jupyverse \
  --disable noauth \
  --disable auth \
  --disable auth_fief \
  --disable auth_jupyterhub
```

The `fps-auth-thinkube` plugin will be auto-discovered via its entry point.

## How It Works

1. User accesses Jupyverse URL
2. Plugin checks for session cookie
3. If no cookie, redirects to JupyterHub OAuth login
4. JupyterHub authenticates user and redirects back with code
5. Plugin exchanges code for token via JupyterHub API
6. User info stored in-memory (not database)
7. Activity reported to JupyterHub for idle culling

## Configuration

The plugin auto-configures from JupyterHub environment variables. Optional settings:

| Option | Description | Default |
|--------|-------------|---------|
| `cookie_name` | Session cookie name | `"jupyverse_thinkube_token"` |

## Differences from fps-auth-jupyterhub

| Feature | fps-auth-jupyterhub | fps-auth-thinkube |
|---------|---------------------|-------------------|
| User storage | SQLAlchemy + aiosqlite | In-memory dict |
| Async issues | MissingGreenlet errors | None |
| Dependencies | SQLAlchemy, aiosqlite | None extra |
| Persistence | Database file | Memory only* |
| Complexity | High | Low |

*User sessions are validated against JupyterHub on each request, so persistence isn't needed.

## License

MIT License
