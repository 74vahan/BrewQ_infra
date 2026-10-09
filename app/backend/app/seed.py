"""`python -m app.seed` - upsert the menu from seed/menu.json."""

import logging
import sys

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.session import create_db_engine, create_session_factory
from app.services.menu_seed import apply_seed, load_seed

log = logging.getLogger("app.seed")


def run_seed() -> None:
    settings = get_settings()
    engine = create_db_engine(settings)
    try:
        factory = create_session_factory(engine)
        with factory() as session:
            result = apply_seed(session, load_seed())
        log.info(
            "Menu seed done: created=%d updated=%d unchanged=%d orphaned=%d",
            result.created,
            result.updated,
            result.unchanged,
            len(result.orphaned),
        )
    finally:
        engine.dispose()


def main() -> int:
    configure_logging(get_settings().log_level)
    run_seed()
    return 0


if __name__ == "__main__":
    sys.exit(main())
