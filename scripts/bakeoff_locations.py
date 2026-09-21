"""Location lookup derived from observed evidence, never test reference answers."""
import re


def location_pattern(seed: str, trace_stdout: str) -> str:
    observed = re.findall(r'^\s{2,}([A-Za-z_$][\w$]*)\s+\d+\s*$', trace_stdout, re.MULTILINE)
    return '|'.join(re.escape(name) for name in sorted(set([seed, *observed])))
