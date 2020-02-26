import ast

from flynt.exceptions import StringEmbeddingTooDeep


class SinSDetector(ast.NodeVisitor):
    def __init__(self, maxdepth):

        self.sns_depth = 0
        self.maxdepth = maxdepth

    def visit_JoinedStr(self, node):
        self.sns_depth += 1
        if self.sns_depth > self.maxdepth:
            raise StringEmbeddingTooDeep

        self.generic_visit(node)
        self.sns_depth -= 1

    def visit_FormattedValue(self, node):
        self.visit(node.value)


def check_sns_depth(node, limit=1):
    d = SinSDetector(limit)
    try:
        d.visit(node)
    except StringEmbeddingTooDeep:
        return False
    else:
        return True
