from textwrap import dedent

def f():
    arg = "text"
    return dedent(
        """\
        some {}
        lorem ipsum
        """.format(arg)
    )
