"""Run with: uv run python -m intellichoice_adapters.seed.seed_mysql"""

import asyncio
import os

from sqlalchemy.engine import make_url

from intellichoice_adapters.seed.mysql_fixtures import seed

DEFAULT_MYSQL_URL = "mysql+aiomysql://intellichoice:intellichoice@localhost:3306"


async def main() -> None:
    mysql_url = os.environ.get("SEED_MYSQL_URL", DEFAULT_MYSQL_URL)
    await seed(mysql_url)
    # Never print the raw URL - a real deployment's SEED_MYSQL_URL carries a live
    # Secrets Manager credential, not the local dev placeholder (found via a real
    # leak into CloudWatch Logs during S32/D-084's first deploy - the password was
    # rotated immediately after).
    print(f"Seeded fixture data into {make_url(mysql_url).render_as_string(hide_password=True)}")


if __name__ == "__main__":
    asyncio.run(main())
