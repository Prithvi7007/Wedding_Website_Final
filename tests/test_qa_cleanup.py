from pathlib import Path


def test_food_and_photo_questions_are_removed():
    template = Path("app/templates/tabs/qa.html").read_text(
        encoding="utf-8"
    )

    assert "Will food be provided?" not in template
    assert "Can I take photos?" not in template
    assert '<span class="qa-category">Food</span>' not in template
    assert '<span class="qa-category">Photos</span>' not in template


def test_remaining_qa_answers_are_preserved():
    template = Path("app/templates/tabs/qa.html").read_text(
        encoding="utf-8"
    )

    expected = [
        "What should I wear?",
        "Can I bring a guest?",
        "Are children invited?",
        "What time should I arrive?",
        "Will parking be available?",
        "Where should I stay?",
        "Who should I contact?",
    ]

    for question in expected:
        assert question in template
