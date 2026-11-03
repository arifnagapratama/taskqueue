"""Container health probe using the configured application token."""
import os
from pathlib import Path
from urllib.request import Request, urlopen

token_file = os.environ.get("TASKQUEUE_TOKEN_FILE")
token = Path(token_file).read_text().strip() if token_file else ""
request = Request("http://127.0.0.1:8080/api/health", headers={"x-api-token": token})
with urlopen(request, timeout=3) as response:
    if response.status != 200:
        raise SystemExit(1)
