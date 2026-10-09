"""Unit of work: commit on success, roll back on any exception."""

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy.orm import Session


@contextmanager
def unit_of_work(session: Session) -> Iterator[Session]:
    """One transaction owned by a service call.

    The session may already have begun a transaction (autobegin), so this helper
    does not call `session.begin()`; it simply ends the transaction either way.
    """
    try:
        yield session
        session.commit()
    except BaseException:
        session.rollback()
        raise
