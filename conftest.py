import sys
from pathlib import Path

# venv site-packages가 sys.path에 확실히 포함되도록 보장
# (pytest binary 직접 실행 시 누락되는 환경 대응)
venv_site = Path(__file__).parent / ".venv" / "lib"
for p in venv_site.glob("python*/site-packages"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
