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
