def percent_conditional(line):
    return "%s\n" % line if not line.endswith('\\') or line.endswith('\\\\') else "%s" % line[:-1]

msg = "{}\nPossible solutions:\n{}".format(msg, "\n".join(solutions))

def format_values(node, values):
    return '{}({})'.format(node.__class__.__name__, ',\n    '.join(values))

self.assertEqual(len(expected), len(result),
    "Unmatched lines. Got:\n{}\nExpected:\n{}".format("\n".join(expected), "\n".join(result)))

self.assertEqual(len(result_lines), len(expected_lines),
    "Unmatched lines. Got:\n{}\nExpected:\n{}".format("\n".join(result_lines), expected))

code.putln("\"{}.{}\",".format(self.full_module_name, classname.replace('"', '')))

"{}".format(b"\n")
