from rest_framework import authentication,exceptions

from .firebase import verify_id_token
from .models import Developer

class FirebaseAuthentication(authentication.BaseAuthentication):
    def authenticate_header(self,request):
        return "Bearer"

    def authenticate(self,request):
        header= request.headers.get("Authentication","")
        parts= header.split()
        if len(parts) !=2 or parts[0].lower() != "bearer":
            return None
        try:
            decoded = verify_id_token(parts[1])
        except Exception as exc:
            raise exceptions.AuthenticationFailed(str(exc)) from exc
        return (Developer.from_claims(decoded),decoded)