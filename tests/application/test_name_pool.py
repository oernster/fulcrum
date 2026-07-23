"""Tests for the shared lead and owner name pool."""

from random import Random

from fulcrum.application.name_pool import NAME_POOL, NamePicker

_MIN_POOL = 200


def test_pool_is_large_unique_and_full_names():
    assert len(NAME_POOL) >= _MIN_POOL
    assert len(set(NAME_POOL)) == len(NAME_POOL)
    assert all(name.strip() and " " in name for name in NAME_POOL)


def test_draw_avoids_repeats_until_the_pool_is_exhausted():
    pool = ("Ada One", "Ben Two", "Cai Three")
    picker = NamePicker(Random(0), pool)
    drawn = {picker.draw() for _ in pool}
    assert drawn == set(pool)


def test_draw_refills_after_exhaustion():
    pool = ("Ada One", "Ben Two")
    picker = NamePicker(Random(0), pool)
    for _ in pool:
        picker.draw()
    assert picker.draw() in pool


def test_draw_is_deterministic_for_a_seeded_rng():
    first = NamePicker(Random(7)).draw()
    second = NamePicker(Random(7)).draw()
    assert first == second


def test_reroll_returns_a_different_name_when_possible():
    picker = NamePicker(Random(3))
    current = picker.draw()
    assert picker.reroll(current) != current


def test_reroll_with_a_single_name_pool_returns_that_name():
    picker = NamePicker(Random(0), ("Ada One",))
    assert picker.reroll("Ada One") == "Ada One"
