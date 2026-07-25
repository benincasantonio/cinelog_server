from app.utils.sanitize_utils import sanitize_failure_detail, strip_html_tags


class TestStripHtmlTags:
    """Tests for the strip_html_tags utility function."""

    # --- Basic HTML tags ---

    def test_strips_script_tag(self):
        assert strip_html_tags("<script>alert(1)</script>") == "alert(1)"

    def test_strips_script_tag_with_attributes(self):
        assert strip_html_tags('<script type="text/javascript">alert(1)</script>') == "alert(1)"

    def test_strips_img_tag_with_onerror(self):
        assert strip_html_tags("<img src=x onerror=alert(1)>") == ""

    def test_strips_bold_tag(self):
        assert strip_html_tags("<b>bold text</b>") == "bold text"

    def test_strips_italic_tag(self):
        assert strip_html_tags("<i>italic</i>") == "italic"

    def test_strips_anchor_tag(self):
        assert strip_html_tags('<a href="http://evil.com">click me</a>') == "click me"

    def test_strips_div_tag(self):
        assert strip_html_tags("<div>content</div>") == "content"

    def test_strips_span_tag(self):
        assert strip_html_tags("<span>text</span>") == "text"

    def test_strips_paragraph_tag(self):
        assert strip_html_tags("<p>paragraph</p>") == "paragraph"

    # --- XSS attack vectors ---

    def test_strips_script_with_encoded_payload(self):
        result = strip_html_tags("<script>document.cookie</script>")
        assert "<script>" not in result
        assert "</script>" not in result

    def test_strips_img_onerror_xss(self):
        assert strip_html_tags('<img src="x" onerror="alert(document.cookie)">') == ""

    def test_strips_svg_onload_xss(self):
        assert strip_html_tags('<svg onload="alert(1)">') == ""

    def test_strips_iframe_tag(self):
        assert strip_html_tags('<iframe src="http://evil.com"></iframe>') == ""

    def test_strips_body_onload_xss(self):
        assert strip_html_tags('<body onload="alert(1)">content</body>') == "content"

    def test_strips_input_onfocus_xss(self):
        assert strip_html_tags('<input onfocus="alert(1)" autofocus>') == ""

    def test_strips_marquee_tag(self):
        assert strip_html_tags('<marquee onstart="alert(1)">text</marquee>') == "text"

    def test_strips_details_ontoggle_xss(self):
        assert strip_html_tags('<details ontoggle="alert(1)" open>xss</details>') == "xss"

    def test_strips_object_tag(self):
        result = strip_html_tags('<object data="data:text/html,<script>alert(1)</script>">')
        assert "<object" not in result
        assert "<script>" not in result
        assert "</script>" not in result

    def test_strips_embed_tag(self):
        assert strip_html_tags('<embed src="http://evil.com/xss.swf">') == ""

    def test_strips_link_tag_with_stylesheet(self):
        assert strip_html_tags('<link rel="stylesheet" href="http://evil.com/evil.css">') == ""

    def test_strips_meta_refresh_xss(self):
        assert strip_html_tags('<meta http-equiv="refresh" content="0;url=http://evil.com">') == ""

    def test_strips_style_tag(self):
        result = strip_html_tags('<style>body{background:url("http://evil.com")}</style>')
        assert "<style>" not in result

    # --- Nested and complex HTML ---

    def test_strips_nested_tags(self):
        assert strip_html_tags("<div><span><b>text</b></span></div>") == "text"

    def test_strips_deeply_nested_script(self):
        result = strip_html_tags("<div><p><script>alert(1)</script></p></div>")
        assert "<script>" not in result
        assert "</script>" not in result

    def test_strips_multiple_tags(self):
        result = strip_html_tags("<b>bold</b> and <i>italic</i>")
        assert result == "bold and italic"

    def test_strips_tag_with_multiple_attributes(self):
        assert strip_html_tags('<a href="http://evil.com" class="link" id="xss">text</a>') == "text"

    # --- Self-closing tags ---

    def test_strips_br_tag(self):
        assert strip_html_tags("line1<br>line2") == "line1line2"

    def test_strips_br_self_closing(self):
        assert strip_html_tags("line1<br/>line2") == "line1line2"

    def test_strips_br_self_closing_with_space(self):
        assert strip_html_tags("line1<br />line2") == "line1line2"

    def test_strips_hr_tag(self):
        assert strip_html_tags("above<hr>below") == "abovebelow"

    # --- Edge cases ---

    def test_plain_text_unchanged(self):
        assert strip_html_tags("Hello, World!") == "Hello, World!"

    def test_empty_string(self):
        assert strip_html_tags("") == ""

    def test_whitespace_only(self):
        assert strip_html_tags("   ") == ""

    def test_preserves_ampersand(self):
        assert strip_html_tags("Tom & Jerry") == "Tom & Jerry"

    def test_preserves_html_entities(self):
        assert strip_html_tags("5 &gt; 3 &amp; 2 &lt; 4") == "5 &gt; 3 &amp; 2 &lt; 4"

    def test_preserves_special_characters(self):
        assert strip_html_tags("Cafe\u0301 & Cre\u0300me") == "Cafe\u0301 & Cre\u0300me"

    def test_preserves_unicode_text(self):
        assert strip_html_tags("Ciao, come stai?") == "Ciao, come stai?"

    def test_preserves_accented_characters(self):
        assert strip_html_tags("Rene\u0301e O'Brien") == "Rene\u0301e O'Brien"

    def test_preserves_numbers_and_punctuation(self):
        assert strip_html_tags("Score: 10/10! Great film.") == "Score: 10/10! Great film."

    def test_strips_leading_trailing_whitespace(self):
        assert strip_html_tags("  hello world  ") == "hello world"

    def test_strips_tags_and_trims(self):
        assert strip_html_tags("  <b>hello</b>  ") == "hello"

    def test_angle_brackets_in_math(self):
        """Mathematical expressions with < and > that don't form valid tags."""
        assert strip_html_tags("3 < 5") == "3 < 5"

    def test_incomplete_tag_not_stripped(self):
        """An incomplete tag (no closing >) should not be stripped."""
        assert strip_html_tags("hello <broken") == "hello <broken"

    def test_multiple_xss_payloads_combined(self):
        payload = "<script>alert(1)</script><img src=x onerror=alert(2)><svg/onload=alert(3)>"
        result = strip_html_tags(payload)
        assert "<script>" not in result
        assert "<img" not in result
        assert "<svg" not in result

    def test_tag_within_text(self):
        assert strip_html_tags("Hello <b>World</b> Foo") == "Hello World Foo"

    # --- Path traversal payloads (stored as-is, but should not contain HTML) ---

    def test_path_traversal_not_affected(self):
        """Path traversal strings contain no HTML, so they pass through unchanged."""
        assert strip_html_tags("../../../etc/passwd") == "../../../etc/passwd"


class TestSanitizeFailureDetail:
    """Tests for the sanitize_failure_detail utility function."""

    def test_collapses_internal_whitespace(self):
        assert sanitize_failure_detail("line one\n\n  line   two\t\tline three") == "line one line two line three"

    def test_strips_leading_and_trailing_whitespace(self):
        assert sanitize_failure_detail("   boom   ") == "boom"

    def test_redacts_embedded_email_addresses(self):
        result = sanitize_failure_detail("delivery to user@example.com failed: connection refused")
        assert "user@example.com" not in result
        assert "[redacted]" in result

    def test_redacts_multiple_email_addresses(self):
        result = sanitize_failure_detail("from admin@example.com to user@example.org failed")
        assert "admin@example.com" not in result
        assert "user@example.org" not in result

    def test_redacts_password_fragment(self):
        result = sanitize_failure_detail("auth failed for password=hunter2")
        assert "hunter2" not in result
        assert "password=[redacted]" in result

    def test_redacts_auth_fragment(self):
        result = sanitize_failure_detail("rejected auth:supersecrettoken by server")
        assert "supersecrettoken" not in result
        assert "auth=[redacted]" in result

    def test_redaction_is_case_insensitive(self):
        result = sanitize_failure_detail("PASSWORD=hunter2")
        assert "hunter2" not in result

    def test_truncates_to_max_length(self):
        result = sanitize_failure_detail("x" * 1000, max_length=500)
        assert len(result) == 500

    def test_uses_max_failure_detail_length_by_default(self):
        result = sanitize_failure_detail("x" * 1000)
        assert len(result) == 500

    def test_short_message_is_unaffected_by_truncation(self):
        assert sanitize_failure_detail("connection refused") == "connection refused"
