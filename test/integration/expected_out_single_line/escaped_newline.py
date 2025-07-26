from textwrap import dedent

def f():
    arg = "text"
    return dedent(
        f"""\
        \
        some {arg}
        lorem ipsum
        """
    )


def f_extra():
    arg = "text"
    return f"""\
    some {arg}\n"""


def f_multiple():
    arg = "text"
    return f"""\
    \
    \
    some {arg}\n"""


def f_single_quotes():
    arg = "text"
    return f'''\
    some {arg}\n'''
