from itertools import product

import pytest

from app.domain.order_status import (
    ACTIVE_STATUSES,
    Actor,
    OrderStatus,
    allowed_targets,
    can_transition,
    is_active,
)

S = OrderStatus

# The complete table from memory/02-database.md (status machine).
EXPECTED = {
    (Actor.BARISTA, S.NEW, S.IN_PROGRESS),
    (Actor.BARISTA, S.IN_PROGRESS, S.READY),
    (Actor.BARISTA, S.READY, S.PICKED_UP),
    (Actor.BARISTA, S.NEW, S.CANCELLED),
    (Actor.BARISTA, S.IN_PROGRESS, S.CANCELLED),
    (Actor.CLIENT, S.NEW, S.CANCELLED),
}


@pytest.mark.parametrize(("actor", "current", "target"), list(product(Actor, S, S)))
def test_every_pair_for_every_actor(actor, current, target):
    assert can_transition(current, target, actor) is ((actor, current, target) in EXPECTED)


def test_all_pairs_are_covered():
    assert len(list(product(Actor, S, S))) == 2 * 5 * 5


@pytest.mark.parametrize("actor", list(Actor))
@pytest.mark.parametrize("terminal", [S.PICKED_UP, S.CANCELLED])
def test_terminal_statuses_have_no_exits(actor, terminal):
    assert allowed_targets(terminal, actor) == ()


def test_no_skipping_and_no_backwards_for_barista():
    assert not can_transition(S.NEW, S.READY, Actor.BARISTA)
    assert not can_transition(S.NEW, S.PICKED_UP, Actor.BARISTA)
    assert not can_transition(S.READY, S.IN_PROGRESS, Actor.BARISTA)
    assert not can_transition(S.READY, S.CANCELLED, Actor.BARISTA)


def test_allowed_targets_order_is_forward_step_then_cancel():
    assert allowed_targets(S.NEW, Actor.BARISTA) == (S.IN_PROGRESS, S.CANCELLED)
    assert allowed_targets(S.IN_PROGRESS, Actor.BARISTA) == (S.READY, S.CANCELLED)
    assert allowed_targets(S.READY, Actor.BARISTA) == (S.PICKED_UP,)
    assert allowed_targets(S.NEW, Actor.CLIENT) == (S.CANCELLED,)


def test_active_statuses():
    assert {S.NEW, S.IN_PROGRESS, S.READY} == ACTIVE_STATUSES
    assert not is_active(S.PICKED_UP)
    assert not is_active(S.CANCELLED)
