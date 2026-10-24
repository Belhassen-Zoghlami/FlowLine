# # from django.shortcuts import render
# from .firebase import register_user,sign_in,verify_id_token,FirebaseAuthError
# from rest_framework import status
# from rest_framework.permissions import AllowAny, IsAuthenticated
# from rest_framework.response import Response
# from rest_framework.views import APIView

# from .models import Developer
# # Create your views here.


# def _payload(developer):
#     return{
#         "id":developer.id,
#         "firebase_uid":developer.firebase_uid,
#         "email":developer.email,
#         "display_name":developer.display_name,
#     }

# class SessionView(APIView):
#     authenticated_classes= []
#     permission_classes =[AllowAny]
#     def post(self,request):
#         id_token=request.data.get("id_token")
#         if not id_token:
#             return Response(
#                 {
#                     "detail":"id_token is required"
#                 },
#                 status=status.HTTP_400_BAD_REQUEST,
#             )
#         try:
#             decoded = verify_id_token(id_token)
#         except Exception as exc:
#             return Response(
#                 {"detail":str(exc)},
#                 status= status.HTTP_401_UNAUTHORIZED,
#             )
#         return Response(_payload(Developer.from_claims(decoded)))


# class RegisterView(APIView):
#     authentication_classes = []
#     permission_classes = [AllowAny]

#     def post(self, request):
#         email = request.data.get("email")
#         password = request.data.get("password")
#         if not email or not password:
#             return Response(
#                 {"detail": "email and password are required."},
#                 status=status.HTTP_400_BAD_REQUEST,
#             )
#         try:
#             uid = register_user(email, password)
#             session = sign_in(email, password)
#         except FirebaseAuthError as exc:
#             return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

#         developer, _ = Developer.objects.get_or_create(
#             firebase_uid=uid, defaults={"email": email}
#         )
#         payload = _payload(developer)
#         payload["id_token"] = session["idToken"]
#         return Response(payload, status=status.HTTP_201_CREATED)

# class LoginView(APIView):
#     authentication_classes=[]
#     permission_classes=[]

#     def post(self,request):
#         email= request.data.get("email")
#         password=request.data.get("password")
#         if not email or not password:
#             return Response(
#                 {"detail":"email and password are required"},
#                 status= status.HTTP_400_BAD_REQUEST,
#             )
#         try:
#             session= sign_in(email,password)
#         except FirebaseAuthError as excep:
#             return Response({"detail":str(excep)},status=status.HTTP_401_UNAUTHORIZED)
#         developer,_=Developer.objects.get_or_create(
#             firebase_uid=session["localId"],
#             defaults={"email":session.get("email",email)},
#         )
#         payload=_payload(developer)
#         payload["id_token"]=session["idToken"]
#         return Response(payload)

# class MeView(APIView):
#     permission_classes =[IsAuthenticated]
#     def get(self,request):
#         return Response(_payload(request.user))



from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from .firebase import FirebaseAuthError, register_user, sign_in, verify_id_token
from .models import Developer

def _payload(developer):
    return {
        "id": developer.id,
        "firebase_uid": developer.firebase_uid,
        "email":developer.email,
        "display_name":developer.display_name,
    }

@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def session_view(request):
    id_token = request.data.get("id_token")
    if not id_token:
        return Response(
            {"detail":"id_token required"},
            status= status.HTTP_400_BAD_REQUEST,
        )
    try:
        decoded= verify_id_token(id_token)
    except Exception as excep:
        return Response(
            {"detail":str(excep)},
            status=status.HTTP_401_UNAUTHORIZED
        )
    return Response(_payload(Developer.from_claims(decoded)))

@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def register_view(request):
    email=request.data.get("email")
    password=request.data.get("password")
    if not email or not password:
        return Response(
            {"detail":"email and password are required"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    try:
        uid=register_user(email,password)
        session=sign_in(email,password)
    except FirebaseAuthError as excep:
        return Response(
            {"detail":str(excep)},
            status=status.HTTP_400_BAD_REQUEST,
        )
    developer,_= Developer.objects.get_or_create(
        firebase_uid=uid,defaults={"email":email}
    )
    payload = _payload(developer)
    payload["id_token"]= session["idToken"]
    return Response(payload, status=status.HTTP_201_CREATED)




@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def login_view(request):
    email=request.data.get("email")
    password= request.data.get("password")
    if not email or not password:
        return Response(
            {"detail":"email and password are required"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    try:
        session=sign_in(email,password)
    except FirebaseAuthError as excep:
        return Response(
            {"detail":str(excep)},
            status=status.HTTP_401_UNAUTHORIZED,
        )
    developer,_=Developer.objects.get_or_create(
        firebase_uid=session["localId"],
        defaults={"email":session.get({"email":email})}
    )
    payload=_payload(developer)
    payload["id_token"] = session["idToken"]
    return Response(payload)
