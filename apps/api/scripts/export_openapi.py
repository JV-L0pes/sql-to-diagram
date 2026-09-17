import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.main import create_app  # noqa: E402

app = create_app()
output_path = Path(__file__).resolve().parents[3] / "packages" / "api-client" / "openapi.json"
output_path.write_text(json.dumps(app.openapi(), indent=2))
print(f"Wrote {output_path}")
