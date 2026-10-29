from quality_gate.gift.why_now import why_now


def test_why_now_follows_the_template_exactly():
    assert why_now("SDR", 3, "We are building our first outbound team") == (
        'SDR posted 3 days ago: "We are building our first outbound team"'
    )


def test_one_day_is_singular():
    assert why_now("SDR", 1, "Hiring now") == 'SDR posted 1 day ago: "Hiring now"'


def test_quote_is_trimmed_to_twelve_words():
    quote = "one two three four five six seven eight nine ten eleven twelve thirteen fourteen"
    line = why_now("AE", 5, quote)
    inner = line.split('"')[1]
    assert inner == "one two three four five six seven eight nine ten eleven twelve…"
    assert len(inner.split()) == 12


def test_whole_line_never_exceeds_twenty_words_even_with_a_long_title():
    title = "Senior Enterprise Account Executive North America East Coast"  # 8 words
    quote = "one two three four five six seven eight nine ten eleven twelve"
    line = why_now(title, 9, quote)
    assert len(line.split()) <= 20
    assert line.startswith(f"{title} posted 9 days ago: \"one")


def test_quote_whitespace_and_wrapping_quotes_are_normalised():
    assert why_now("SDR", 2, '  "Build   the\nteam"  ') == 'SDR posted 2 days ago: "Build the team"'


def test_contact_data_in_the_quote_is_removed():
    line = why_now("SDR", 2, "Email jane.doe@acme.com or call +1 (415) 555-0134 to apply")
    assert "@" not in line
    assert "555" not in line
    assert "415" not in line
