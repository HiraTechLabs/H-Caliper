import os

from sqlalchemy.engine import URL, make_url


def database_url_from_environment() -> URL:
    direct_url = os.environ.get("CALIPER_DATABASE_URL")
    if direct_url:
        return make_url(direct_url)

    username = os.environ.get("CALIPER_DB_USER")
    password = os.environ.get("CALIPER_DB_PASSWORD")
    host = os.environ.get("CALIPER_DB_HOST")
    database = os.environ.get("CALIPER_DB_NAME")
    if not all((username, password, host, database)):
        raise RuntimeError(
            "Set CALIPER_DATABASE_URL or CALIPER_DB_USER, CALIPER_DB_PASSWORD, "
            "CALIPER_DB_HOST, and CALIPER_DB_NAME"
        )

    return URL.create(
        "postgresql+psycopg",
        username=username,
        password=password,
        host=host,
        port=int(os.environ.get("CALIPER_DB_PORT", "5432")),
        database=database,
    )
