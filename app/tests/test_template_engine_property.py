"""Property-based tests for Template Engine.

Feature: email-scheduler-tracker
Tests Properties 1, 2, 3, and 4 from the design document.
"""

import re

from hypothesis import given, settings, strategies as st, assume

from app.services.template_engine import (
    TemplateData,
    serialize_template,
    deserialize_template,
    validate_template,
    render_template,
    PLACEHOLDER_PATTERN,
)


# --- Strategies ---

# Valid placeholder field names: alphanumeric + underscore, non-empty
field_name_st = st.from_regex(r"[a-zA-Z_]\w{0,19}", fullmatch=True)

# Plain text that does NOT contain {{ or }} to avoid accidental placeholder patterns
plain_text_st = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N", "P", "Z", "S"),
        blacklist_characters="{}"
    ),
    min_size=0,
    max_size=100,
)

# Template name: non-empty printable string
template_name_st = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), min_codepoint=48, max_codepoint=122),
    min_size=1,
    max_size=30,
)


def _build_template_text(parts):
    """Build a template string from alternating plain text and placeholder segments."""
    return "".join(parts)


def template_text_with_placeholders_st(min_placeholders=0, max_placeholders=5):
    """Generate template text with a known set of valid placeholders interspersed with plain text."""
    return st.lists(
        field_name_st, min_size=min_placeholders, max_size=max_placeholders
    ).flatmap(lambda fields: st.tuples(
        st.just(fields),
        st.lists(plain_text_st, min_size=len(fields) + 1, max_size=len(fields) + 1),
    )).map(lambda pair: _interleave(pair[1], pair[0]))


def _interleave(texts, fields):
    """Interleave plain texts with {{field}} placeholders, returning (result_string, field_names)."""
    parts = []
    for i, text in enumerate(texts):
        parts.append(text)
        if i < len(fields):
            parts.append("{{" + fields[i] + "}}")
    return ("".join(parts), list(dict.fromkeys(fields)))  # deduplicated, ordered


# Strategy that produces (subject_str, body_str, all_unique_field_names)
template_with_fields_st = st.tuples(
    template_text_with_placeholders_st(0, 3),
    template_text_with_placeholders_st(0, 3),
).map(lambda pair: (
    pair[0][0],  # subject text
    pair[1][0],  # body text
    list(dict.fromkeys(pair[0][1] + pair[1][1])),  # all unique field names
))


# --- Property 1: Template serialization round trip ---
# Feature: email-scheduler-tracker, Property 1: Template serialization round trip
# **Validates: Requirements 2.5, 2.6**

@given(
    name=template_name_st,
    subject=st.text(min_size=0, max_size=100),
    body=st.text(min_size=0, max_size=200),
)
@settings(max_examples=100)
def test_template_serialization_round_trip(name: str, subject: str, body: str):
    """For any valid Template, serialize then deserialize should produce
    an equivalent Template with all Dynamic_Field placeholders intact."""
    original = TemplateData(name=name, subject=subject, body=body)

    json_str = serialize_template(original)
    restored = deserialize_template(json_str)

    assert restored.name == original.name
    assert restored.subject == original.subject
    assert restored.body == original.body


# --- Property 2: Placeholder validation ---
# Feature: email-scheduler-tracker, Property 2: Placeholder validation
# **Validates: Requirements 2.1, 2.4**

# Malformed placeholder patterns: contain spaces, special chars, or are empty
malformed_inner_st = st.one_of(
    st.just(""),                          # empty: {{}}
    st.text(                              # contains spaces or special chars
        alphabet=st.characters(whitelist_categories=("L", "N", "P", "Z"), min_codepoint=32, max_codepoint=126,
                               blacklist_characters="{}"),
        min_size=1,
        max_size=20,
    ).filter(lambda s: not re.fullmatch(r"\w+", s)),  # must NOT be a valid field name
)


@given(fields=st.lists(field_name_st, min_size=1, max_size=5))
@settings(max_examples=100)
def test_placeholder_validation_accepts_valid(fields: list[str]):
    """For any set of valid placeholder field names, validation should accept them all."""
    subject = " ".join(f"{{{{{f}}}}}" for f in fields[:2])
    body = " ".join(f"{{{{{f}}}}}" for f in fields[2:])

    result = validate_template(subject, body)

    assert result.valid is True
    assert len(result.invalid_placeholders) == 0
    # All unique field names should appear in valid_placeholders
    unique_fields = list(dict.fromkeys(fields))
    for f in unique_fields:
        assert f in result.valid_placeholders


@given(bad_inner=malformed_inner_st)
@settings(max_examples=100)
def test_placeholder_validation_rejects_malformed(bad_inner: str):
    """For any malformed placeholder pattern, validation should reject it."""
    text = f"Hello {{{{{bad_inner}}}}} world"
    result = validate_template(text, "")

    assert result.valid is False
    assert len(result.invalid_placeholders) > 0


# --- Property 3: Complete template rendering removes all placeholders ---
# Feature: email-scheduler-tracker, Property 3: Complete template rendering removes all placeholders
# **Validates: Requirements 2.2**

@given(data=template_with_fields_st, values=st.dictionaries(
    keys=field_name_st,
    values=plain_text_st.filter(lambda s: "{{" not in s),
    min_size=0,
    max_size=10,
))
@settings(max_examples=100)
def test_complete_rendering_removes_all_placeholders(data, values):
    """For any Template and complete context, rendered output has zero
    unresolved {{...}} placeholders."""
    subject, body, field_names = data

    # Build a complete context: ensure every field name has a value
    context = {}
    for f in field_names:
        context[f] = values.get(f, "replacement")

    result = render_template(subject, body, context)

    assert result.success is True
    assert result.rendered is not None
    # No unresolved placeholders in output
    assert "{{" not in result.rendered.subject
    assert "{{" not in result.rendered.body
    assert "}}" not in result.rendered.subject
    assert "}}" not in result.rendered.body


# --- Property 4: Incomplete context rendering reports missing fields ---
# Feature: email-scheduler-tracker, Property 4: Incomplete context rendering reports missing fields
# **Validates: Requirements 2.3**

@given(data=template_with_fields_st)
@settings(max_examples=100)
def test_incomplete_context_reports_missing_fields(data):
    """For any Template with placeholders and incomplete context,
    render reports exactly the missing field names."""
    subject, body, field_names = data
    assume(len(field_names) >= 2)  # need at least 2 fields to make one missing

    # Provide values for all fields except the last one
    provided = field_names[:-1]
    missing_expected = [field_names[-1]]

    # Only include provided fields if they are not the same as the missing one
    context = {f: "value" for f in provided if f != field_names[-1]}

    # Recompute expected missing: any field not in context
    expected_missing = sorted(set(field_names) - set(context.keys()))
    assume(len(expected_missing) > 0)

    result = render_template(subject, body, context)

    assert result.success is False
    assert sorted(result.missing_fields) == expected_missing
