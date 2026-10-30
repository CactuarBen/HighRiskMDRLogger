# Requirements 
- Ruff
- ISort
- httpx2 (installed with `pip install -e ".[dev]"`). Starlette's `TestClient` imports `httpx2` for type checking, so without it Pylance reports `Type of "post" is unknown` on every `client.post`/`client.get` in the tests
-.vscode/settings.json to follow

```json
  "python.defaultInterpreterPath": ".venv/bin/python",
  "python.analysis.typeCheckingMode": "strict",
  "python.analysis.extraPaths": [
    "02-compliance-logging-sdk",
    "01-compliance-adapter",
    "03-compliance-forwarder",
    "04-compliance-backend"
  ]
```