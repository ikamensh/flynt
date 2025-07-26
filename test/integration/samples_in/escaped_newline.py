from textwrap import dedent

def f():
    arg = "text"
    return dedent(
        """\
        \
        some {}
        lorem ipsum
        """.format(arg)
    )


def f_extra():
    arg = "text"
    return """\
    some {}\n""".format(arg)


def f_multiple():
    arg = "text"
    return """\
    \
    \
    some {}\n""".format(arg)


def f_single_quotes():
    arg = "text"
    return '''\
    some {}\n'''.format(arg)
