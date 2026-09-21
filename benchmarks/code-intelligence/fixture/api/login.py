from auth.service import AuthService


def login_request(token: str) -> bool:
    service = AuthService()
    return service.authenticate(token)
