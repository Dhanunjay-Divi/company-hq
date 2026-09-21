from api.login import login_request


def handle_login(token: str) -> str:
    return "ok" if login_request(token) else "unauthorized"
