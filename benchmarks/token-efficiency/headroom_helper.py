#!/usr/bin/env python3
from pathlib import Path
import sys
from headroom import compress, CompressConfig

src=Path(sys.argv[1]).read_text()
cfg=CompressConfig(
    compress_user_messages=False,
    protect_recent=0,
    protect_analysis_context=False,
    min_tokens_to_compress=1,
    kompress_model="disabled",
)
messages=[
    {"role":"user","content":"Inspect this tool output and preserve failure evidence."},
    {"role":"tool","content":src},
]
result=compress(messages, model="gpt-4o", config=cfg)
parts=[]
for message in result.messages:
    if message.get("role")=="tool":
        value=message.get("content","")
        if isinstance(value,str): parts.append(value)
        elif isinstance(value,list):
            for item in value:
                if isinstance(item,dict) and isinstance(item.get("text"),str): parts.append(item["text"])
Path(sys.argv[2]).write_text("\n".join(parts))
