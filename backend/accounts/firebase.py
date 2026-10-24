import firebase_admin
import requests
from django.conf import settings
from firebase_admin import auth as firebase_auth
from firebase_admin import credentials

_IDENTITY_TOOLKIT = "https://identitytoolkit.googleapis.com/v1/accounts"

_firebase_app = None


class FirebaseAuthError(Exception):
    """Raised when Firebase refuses a registration or a login."""


def _get_app():
    global _firebase_app
    if _firebase_app is None:
        cred_path = settings.FIREBASE_CREDENTIALS
        if cred_path:
            cred = credentials.Certificate(cred_path)
            _firebase_app = firebase_admin.initialize_app(cred)
        else:
            _firebase_app = firebase_admin.initialize_app()
    return _firebase_app


def verify_id_token(id_token):
    return firebase_auth.verify_id_token(id_token, app=_get_app(), check_revoked=True)

def revoke_tokens(uid): #revokes all tokens for a user
    firebase_auth.revoke_refresh_tokens(uid, app=_get_app())

def register_user(email, password):
    """Create the account with the Admin SDK, which bypasses the sign-up toggle."""
    try:
        user = firebase_auth.create_user(email=email, password=password, app=_get_app())
    except Exception as exc:
        raise FirebaseAuthError(str(exc)) from exc
    return user.uid


def sign_in(email, password):
    """Exchange an email and password for a fresh Firebase ID token."""
    api_key = settings.FIREBASE_API_KEY
    if not api_key:
        raise FirebaseAuthError("FIREBASE_API_KEY is not configured.")
    response = requests.post(
        f"{_IDENTITY_TOOLKIT}:signInWithPassword",
        params={"key": api_key},
        json={"email": email, "password": password, "returnSecureToken": True},
        timeout=15,
    )
    data = response.json()
    if response.status_code != 200 or "idToken" not in data:
        message = data.get("error", {}).get("message", "Authentication failed.")
        raise FirebaseAuthError(message)
    return data
