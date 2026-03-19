import jwt
from django.conf import settings
import datetime
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed


def create_token(payload, timeout=120):
    # Add an expiration time limit to incoming business data
    payload["exp"] = datetime.datetime.utcnow() + datetime.timedelta(minutes=timeout)
    # Define secret value
    secret = settings.SECRET_KEY
    # The default irreversible encryption algorithm is HS256
    token = jwt.encode(payload=payload, key=secret)
    return token


class JWTAuthentication(BaseAuthentication):
    def authenticate(self, request):
        Response = {}
        Response["data"] = ""
        secret = settings.SECRET_KEY
        try:
            TokenString = str(request.META["HTTP_AUTHORIZATION"])[7:]
            payload = jwt.decode(TokenString, key=secret, algorithms="HS256")
            # print(payload)
            request.email = payload["email"]
            request.user_id = payload["user_id"]
            request.role = payload["role"]

        except jwt.InvalidTokenError as error:
            if str(error) == "Signature has expired":
                Response["msg"] = "Your session is expired. Please login again"
                Response["error"] = 100
                raise AuthenticationFailed(Response)
            else:
                Response["msg"] = "Unauthorised request(101)"
                Response["error"] = 100
                raise AuthenticationFailed(Response)
        except jwt.DecodeError:
            Response["msg"] = "Unauthorised request(102)"
            Response["error"] = 100
            raise AuthenticationFailed(Response)
        except Exception:
            Response["msg"] = "Unauthorised request(102)"
            Response["error"] = 100
            raise AuthenticationFailed(Response)

        return payload.get("user_id"), TokenString


class JWTAuthenticationUrl(BaseAuthentication):
    def authenticate(self, request):
        Response = {}
        Response["data"] = ""
        secret = settings.SECRET_KEY
        print(request)
        print("SS\n", secret)
        try:

            TokenString = request.query_params.get("token")
            payload = jwt.decode(TokenString, key=secret, algorithms="HS256")

        except jwt.InvalidTokenError as error:
            if str(error) == "Signature has expired":
                Response["errorMsg"] = "Your session is expired. Please login again"
                Response["error"] = 100
                raise AuthenticationFailed(Response)
            else:
                Response["errorMsg"] = "Unauthorised request(101)"
                Response["error"] = 100
                raise AuthenticationFailed(Response)
        except jwt.DecodeError:
            Response["errorMsg"] = "Unauthorised request(102)"
            Response["error"] = 100
            raise AuthenticationFailed(Response)

        return payload.get("user_id"), TokenString
