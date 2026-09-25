"""Classify native error fields only; never inspect model-generated replies."""
import re


def quota_failure(error):
    if isinstance(error, dict):
        code = str(error.get('code') or error.get('type') or error.get('codexErrorInfo') or '')
        text = str(error.get('message') or '')
    else:
        code, text = '', str(error or '')
    known = {'usageLimitExceeded', 'rate_limit_exceeded', 'insufficient_quota', 'quota_exceeded'}
    if code in known or re.search(r'usage limit|quota (?:exceeded|exhausted)|rate.limit (?:exceeded|reached)|hit your.*limit', text, re.I):
        return {'source': 'native-provider', 'kind': 'quota_exhausted'}
    return None
