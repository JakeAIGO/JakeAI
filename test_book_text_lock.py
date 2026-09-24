from book_text_lock import require_exact, verify_exact

def test_exact_text_passes():
    original = "The Time Traveller had finally finished.\n".encode("utf-8")
    assert verify_exact(original, original).exact is True

def test_one_word_substitution_fails():
    original = "the machine".encode("utf-8")
    changed = "a machine".encode("utf-8")
    result = verify_exact(original, changed)
    assert result.exact is False
    assert result.first_difference is not None

def test_punctuation_change_fails():
    original = "Stop.".encode("utf-8")
    changed = "Stop!".encode("utf-8")
    assert verify_exact(original, changed).exact is False

def test_whitespace_change_fails():
    original = "one  two".encode("utf-8")
    changed = "one two".encode("utf-8")
    assert verify_exact(original, changed).exact is False

def test_require_exact_raises():
    try:
        require_exact(b"the", b"a")
    except ValueError:
        return
    raise AssertionError("expected exact-text invariant to reject modified text")
