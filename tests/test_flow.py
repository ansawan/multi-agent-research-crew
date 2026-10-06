from src.flow import parse_qa_response, extract_sources_from_markdown, markdown_to_styled_html


def test_qa_json_verdict_is_respected():
    qa = parse_qa_response('{"approved": true, "score": 9.1, "issues": [], "required_fixes": []}')
    assert qa.approved is True
    assert qa.score == 9.1


def test_qa_json_in_code_fence():
    raw = '```json\n{"approved": false, "score": 6.5, "issues": ["missing citation"], "required_fixes": ["add [2]"]}\n```'
    qa = parse_qa_response(raw)
    assert qa.approved is False
    assert qa.issues == ["missing citation"]
    assert qa.required_fixes == ["add [2]"]


def test_qa_missing_approved_uses_score_threshold():
    assert parse_qa_response('{"score": 5}').approved is False
    assert parse_qa_response('{"score": 8.5}').approved is True


def test_qa_unparseable_response_is_not_approved():
    qa = parse_qa_response("I could not review this draft.")
    assert qa.approved is False
    assert qa.required_fixes


def test_qa_text_score_is_extracted_and_clamped():
    assert parse_qa_response("Score: 7.5 - needs work").score == 7.5
    assert parse_qa_response("score: 85").score == 10.0


def test_extract_sources_dedupes_links_and_plain_urls():
    md = (
        "See [Report](https://a.com/x) and https://a.com/x.\n"
        "## Sources\n1. https://b.org/page, more text"
    )
    assert extract_sources_from_markdown(md) == ["https://a.com/x", "https://b.org/page"]


def test_html_report_renders_tables_and_escapes_title():
    md = "# Title\n\n| A | B |\n|---|---|\n| 1 | 2 |\n"
    out = markdown_to_styled_html(md, "<script>x</script>")
    assert "<table>" in out
    assert "<title>&lt;script&gt;x&lt;/script&gt; - Research Report</title>" in out
