from auth.token import verify_token


class AuthService:
    def authenticate(self, token: str) -> bool:
        return verify_token(token)
