from dataclasses import dataclass

@dataclass
class Session:
    user_id: str
    role: str

def validate_token(token: str) -> Session:
    if token != "fixture-token":
        raise ValueError("invalid token")
    return Session(user_id="user-1", role="admin")

def check_permission(session: Session, permission: str) -> bool:
    return session.role == "admin" and permission == "reports:read"

def authorize_session(token: str, permission: str) -> Session:
    session = validate_token(token)
    if not check_permission(session, permission):
        raise PermissionError(permission)
    return session
