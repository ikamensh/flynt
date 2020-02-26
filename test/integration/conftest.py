import pytest

all_files = pytest.fixture(
    params=[
        "CantAffordActiveException.py",
        "all_named.py",
        "def_empty_line.py",
        "digit_ordering.py",
        "dict_func.py",
        "double_conv.py",
        "escaped_dq.py",
        "first_string.py",
        "hard_percent.py",
        "implicit_concat.py",
        "implicit_concat_comment.py",
        "implicit_concat_named1.py",
        "implicit_concat_named2.py",
        "indexed_fmt_name.py",
        "indexed_percent.py",
        "long.py",
        "multiline.py",
        "multiline_1.py",
        "multiline_2.py",
        "multiline_3.py",
        "multiline_twice.py",
        "multiple.py",
        "multiline_keep.py",
        "named_inverse.py",
        "no_fstring_1.py",
        "no_fstring_2.py",
        "percent_dict.py",
        "percent_numerics.py",
        "percent_op.py",
        "percent_strings.py",
        "raw_string.py",
        "regression_flask.py",
        "simple.py",
        "simple_comment.py",
        "simple_docstring.py",
        "simple_format.py",
        "simple_format_double_brace.py",
        "simple_indent.py",
        "simple_percent.py",
        "simple_percent_comment.py",
        "simple_start.py",
        "simple_str_newline.py",
        "simple_str_return.py",
        "simple_str_tab.py",
        "slash_quotes.py",
        "some_named.py",
        "string_in_string.py",
        "str_literal.py",
        "tuple_in_list.py",
        "two_liner.py",
    ]
)

# @pytest.fixture(params=[
# "escaped_dq.py",
# ])
@all_files
def filename(request):
    yield request.param


all_files_concat = pytest.fixture(
    params=[
        "multiple.py",
        "parens.py",
        "no_parens.py",
        "index.py",
        "mixed_format.py",
        "longer_line.py",
    ]
)

# @pytest.fixture(params=["mixed_format.py"])
@all_files_concat
def filename_concat(request):
    yield request.param
