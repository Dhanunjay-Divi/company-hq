from auth.session import authorize_session

def get_report(token: str, report_id: str) -> dict:
    session = authorize_session(token, "reports:read")
    return {"report_id": report_id, "requested_by": session.user_id}

def export_report(token: str, report_id: str) -> str:
    report = get_report(token, report_id)
    return f"{report['report_id']}:{report['requested_by']}"
