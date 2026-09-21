def normalize_token(token: str) -> str:
    return token.strip()


def verify_token(token: str) -> bool:
    normalized = normalize_token(token)
    return normalized == "company-hq-secret"
