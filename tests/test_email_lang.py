"""Email cleaning and script detection utilities."""

from openjev.email import clean_email_body
from openjev.lang import analyse, detect_script, guess_latin_language


def test_clean_email_body_strips_quotes_signatures_and_disclaimers():
    body = (
        "Please refund the duplicate charge today.\n"
        "\n"
        "Thanks,\nAlex\n"
        "-- \nSent from my iPhone\n"
        "On Monday, support wrote:\n> have you tried turning it off?\n"
        "This email is confidential and intended solely for the named addressee."
    )
    cleaned = clean_email_body(body)
    assert "refund the duplicate charge" in cleaned
    assert "turning it off" not in cleaned
    assert "iPhone" not in cleaned
    assert "confidential" not in cleaned


def test_detect_script_and_language():
    assert detect_script("Charged twice, need a refund please") == "latin"
    assert detect_script("मुझसे दो बार शुल्क लिया गया") == "devanagari"
    assert detect_script("12345 !!!") == "unknown"
    assert guess_latin_language("the customer was charged twice and they want a refund please") == "en"
    assert guess_latin_language("Der Kunde wurde zweimal belastet und bitte um Hilfe") == "de"


def test_analyse_flags_non_english_state():
    english = analyse("I was charged twice and need a refund for my invoice today.")
    assert english["script"] == "latin" and english["is_english"] is True
    hindi = analyse("मुझसे दो बार शुल्क लिया गया, कृपया पैसे वापस करें।")
    assert hindi["script"] == "devanagari" and hindi["is_english"] is False
