"""Write ch14/langfuse/.env, which docker compose reads beside compose.yml: a random value for every secret
Langfuse's compose file marks CHANGEME, and the organization, project, API keys and user that Langfuse creates
on its first start, so the lab needs no sign-up. The programs that send runs to Langfuse read the same file.

    uv run python ch14/langfuse/new_env.py

Run it once, before the first `docker compose up`. The secrets are fixed when the volumes are first created.
"""

import secrets
from pathlib import Path

ENV = Path(__file__).parent / ".env"
if ENV.exists():
    raise SystemExit(
        f"{ENV} exists. To start again: docker compose down -v, then delete it."
    )

postgres, minio = secrets.token_hex(16), secrets.token_hex(16)
public, secret = f"pk-lf-{secrets.token_hex(16)}", f"sk-lf-{secrets.token_hex(16)}"
values = {
    "TELEMETRY_ENABLED": "false",  # the compose file's default sends usage data to Langfuse
    "SALT": secrets.token_hex(16),
    "ENCRYPTION_KEY": secrets.token_hex(32),
    "NEXTAUTH_SECRET": secrets.token_hex(32),
    "POSTGRES_PASSWORD": postgres,
    "DATABASE_URL": f"postgresql://postgres:{postgres}@postgres:5432/postgres",
    "CLICKHOUSE_PASSWORD": secrets.token_hex(16),
    "REDIS_AUTH": secrets.token_hex(16),
    "MINIO_ROOT_PASSWORD": minio,
    "LANGFUSE_S3_EVENT_UPLOAD_SECRET_ACCESS_KEY": minio,
    "LANGFUSE_S3_MEDIA_UPLOAD_SECRET_ACCESS_KEY": minio,
    "LANGFUSE_S3_BATCH_EXPORT_SECRET_ACCESS_KEY": minio,
    "LANGFUSE_INIT_ORG_ID": "cobalt",
    "LANGFUSE_INIT_ORG_NAME": "Cobalt Freight",
    "LANGFUSE_INIT_PROJECT_ID": "investigation",
    "LANGFUSE_INIT_PROJECT_NAME": "Exception investigation",
    "LANGFUSE_INIT_PROJECT_PUBLIC_KEY": public,
    "LANGFUSE_INIT_PROJECT_SECRET_KEY": secret,
    "LANGFUSE_INIT_USER_EMAIL": "analyst@cobalt.example",
    "LANGFUSE_INIT_USER_NAME": "Analyst",
    "LANGFUSE_INIT_USER_PASSWORD": secrets.token_urlsafe(12),
    # What the programs read: the names Langfuse's own SDK uses
    "LANGFUSE_BASE_URL": "http://localhost:3000",
    "LANGFUSE_PUBLIC_KEY": public,
    "LANGFUSE_SECRET_KEY": secret,
}
ENV.write_text("".join(f"{name}={value}\n" for name, value in values.items()))
ENV.chmod(0o600)
print(f"Wrote {ENV}. Sign in as analyst@cobalt.example with the password in it.")
