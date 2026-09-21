#!/usr/bin/env python3
"""Deterministic token-efficiency bake-off for Company HQ.

Compares raw output, RTK, and Headroom on synthetic noisy tool outputs.
No provider/model call is made. Headroom is configured with Kompress disabled,
so only local structural/deterministic compression paths are allowed.
"""
from __future__ import annotations

import argparse, json, math, os, subprocess, sys, tempfile, time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

def token_proxy(text: str) -> int:
    return math.ceil(len(text.encode("utf-8")) / 4)

def fixtures() -> dict[str, tuple[str, list[str]]]:
    log_lines = [f"2026-09-20T12:{i%60:02d}:00Z INFO worker-{i%8} heartbeat ok latency={20+i%7}ms" for i in range(240)]
    log_lines[173] = "2026-09-20T12:53:00Z FATAL auth/token.py:17 token validation failed code=E401 request=req-7f3a"
    test_lines = [f"tests/test_api.py::test_case_{i:03d} PASSED" for i in range(180)]
    test_lines += [
        "tests/test_auth.py::test_expired_token FAILED",
        "E   AssertionError: expected status=401 got=200",
        "E   at auth/token.py:17 code=E401",
        "================== 1 failed, 180 passed in 4.21s ==================",
    ]
    rows=[{"id":i,"status":"ok","region":"us-east-1","latency_ms":20+(i%5),"meta":{"source":"fixture","attempt":1}} for i in range(220)]
    rows[137]={"id":137,"status":"error","region":"us-east-1","latency_ms":913,"error_code":"E401","file":"auth/token.py","line":17,"request_id":"req-7f3a"}
    json_text=json.dumps({"results":rows,"summary":{"count":220,"errors":1}},indent=2)
    return {
        "logs":("\n".join(log_lines)+"\n",["FATAL","auth/token.py:17","E401","req-7f3a"]),
        "tests":("\n".join(test_lines)+"\n",["test_expired_token","AssertionError","auth/token.py:17","E401","1 failed"]),
        "json":(json_text+"\n",['"status": "error"','"error_code": "E401"','"file": "auth/token.py"','"request_id": "req-7f3a"']),
    }

def record(method:str,name:str,before:str,after:str,markers:list[str],seconds:float,error:str|None=None)->dict[str,Any]:
    before_b=len(before.encode()); after_b=len(after.encode())
    return {
        "method":method,"fixture":name,"available":error is None,"error":error,
        "seconds":round(seconds,4),"before_bytes":before_b,"after_bytes":after_b,
        "before_token_proxy":token_proxy(before),"after_token_proxy":token_proxy(after),
        "reduction_pct":round((1-after_b/max(1,before_b))*100,2),
        "evidence_preserved":all(m in after for m in markers),
        "missing_markers":[m for m in markers if m not in after],
        "output_tail":after[-2000:],
    }

def run_cmd(cmd:list[str],cwd:Path,timeout:int=60)->tuple[int,str,str,float]:
    t=time.perf_counter()
    try:
        p=subprocess.run(cmd,cwd=cwd,capture_output=True,text=True,timeout=timeout,check=False)
        return p.returncode,p.stdout,p.stderr,time.perf_counter()-t
    except Exception as e:
        return 127,"",str(e),time.perf_counter()-t

def rtk_result(rtk:str,name:str,text:str,markers:list[str],work:Path)->dict[str,Any]:
    if not rtk:
        return record("rtk",name,text,"",markers,0,"RTK_BIN not configured")
    source=work/f"{name}.txt"; source.write_text(text)
    if name=="json":
        cmd=[rtk,"json",str(source),"-d","2"]
    else:
        emit=work/"emit.py"
        if not emit.exists():
            emit.write_text("import pathlib,sys; p=pathlib.Path(sys.argv[1]); print(p.read_text(), end='')\n")
        mode="err" if name=="logs" else "test"
        cmd=[rtk,mode,sys.executable,str(emit),str(source)]
    rc,out,err,sec=run_cmd(cmd,work)
    if rc not in (0,1):
        return record("rtk",name,text,out+err,markers,sec,f"rtk exit {rc}")
    return record("rtk",name,text,out+err,markers,sec)

def headroom_result(py:str,name:str,text:str,markers:list[str],work:Path)->dict[str,Any]:
    if not py:
        return record("headroom",name,text,"",markers,0,"HEADROOM_PYTHON not configured")
    source=work/f"headroom-{name}.txt"; dest=work/f"headroom-{name}.out"
    source.write_text(text)
    helper=Path(__file__).with_name("headroom_helper.py")
    rc,out,err,sec=run_cmd([py,str(helper),str(source),str(dest)],work,120)
    if rc!=0 or not dest.exists():
        return record("headroom",name,text,out+err,markers,sec,f"headroom exit {rc}")
    return record("headroom",name,text,dest.read_text(),markers,sec)

def markdown(rows:list[dict[str,Any]])->str:
    lines=["# Token-efficiency bake-off","",
      "Deterministic local fixtures. Token proxy is bytes/4 and is not provider billing.","",
      "| Method | Fixture | Evidence | Reduction | Token proxy before → after | Seconds |",
      "| --- | --- | --- | ---: | ---: | ---: |"]
    for r in rows:
        lines.append(f"| {r['method']} | {r['fixture']} | {'yes' if r['evidence_preserved'] else 'NO'} | {r['reduction_pct']}% | {r['before_token_proxy']} → {r['after_token_proxy']} | {r['seconds']} |")
    lines+=["","Adoption rule: a compressor is ineligible for an automatic path if any required failure/evidence marker is lost. Proxy/auth rewriting is outside this benchmark and remains disabled by default.",""]
    return "\n".join(lines)

def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument("--output",type=Path,default=Path("token-efficiency-results.json")); ap.add_argument("--markdown",type=Path,default=Path("token-efficiency-results.md")); args=ap.parse_args()
    rows=[]
    with tempfile.TemporaryDirectory(prefix="hq-token-bench-") as td:
        work=Path(td)
        for name,(text,markers) in fixtures().items():
            rows.append(record("raw",name,text,text,markers,0))
            rows.append(rtk_result(os.environ.get("RTK_BIN",""),name,text,markers,work))
            rows.append(headroom_result(os.environ.get("HEADROOM_PYTHON",""),name,text,markers,work))
    payload={"schema":1,"results":rows}
    args.output.write_text(json.dumps(payload,indent=2)+"\n")
    rendered=markdown(rows); args.markdown.write_text(rendered+"\n"); print(rendered); print("\nJSON:",args.output)
    # Benchmark job fails if an available compressor loses required evidence.
    bad=[r for r in rows if r["method"]!="raw" and r["available"] and not r["evidence_preserved"]]
    return 2 if bad else 0

if __name__=="__main__": raise SystemExit(main())
