shared_state = {
    "initialized": False
}


def test_a_initialize():
    shared_state["initialized"] = True
    assert shared_state["initialized"] is True


def test_b_requires_initialization():
    assert shared_state["initialized"] is True


def test_c_independent_calculation():
    assert 10 + 20 == 30