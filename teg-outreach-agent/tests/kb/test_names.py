from app.kb._names import _norm, _token_set_ratio


def test_norm_strips_legal_suffixes_and_punct():
    assert _norm("Third Rock Techkno Pvt. Ltd.") == "third rock techkno"


def test_token_set_ratio_exact_and_partial():
    assert _token_set_ratio("Third Rock Techkno", "third rock techkno") == 1.0
    assert 0.0 < _token_set_ratio("Third Rock", "Third Rock Techkno") < 1.0
    assert _token_set_ratio("", "anything") == 0.0
