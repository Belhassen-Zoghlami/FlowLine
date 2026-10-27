import requests
from django.conf import settings

def get(path, token="", **params):
    headers ={
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": settings.GITHUB_API_VERSION,
        "User-Agent": "FlowLine-CI",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return requests.get(f"{settings.GITHUB_API_BASE}{path}",
                        headers=headers,
                        params=params,
                        timeout=settings.GITHUB_API_TIMEOUT,
                        )