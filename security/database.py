def get_db_connection(use_async=True):
    TEMP_DB_LOC = "dev.db"
    ASYNC_TEMP_DATABASE_URL = f"sqlite+aiosqlite:///./{TEMP_DB_LOC}"
    TEMP_DATABASE_URL = f"sqlite:///./{TEMP_DB_LOC}"
    url = ASYNC_TEMP_DATABASE_URL if use_async else TEMP_DATABASE_URL
    return url