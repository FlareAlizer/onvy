import sys
from pathlib import Path

# gpu-node/ — отдельный деплоюмент, не пакет основного репозитория; добавляем
# его в sys.path, чтобы `import app` резолвился в gpu-node/app.py независимо
# от того, откуда запущен pytest.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
