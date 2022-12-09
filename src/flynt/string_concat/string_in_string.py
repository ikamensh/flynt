import ast

from flynt.exceptions import StringEmbeddingTooDeep


class SinSDetector(ast.NodeVisitor):
    def __init__(self, maxdepth: int) -> None:

        self.sns_depth = 0
        self.maxdepth = maxdepth

    def visit_JoinedStr(self, node: ast.JoinedStr) -> None:
        self.sns_depth += 1
        if self.sns_depth > self.maxdepth:
            raise StringEmbeddingTooDeep(
                f"String embedding too deep: {self.sns_depth} > {self.maxdepth}",
            )

        self.generic_visit(node)
        self.sns_depth -= 1

    def visit_FormattedValue(self, node: ast.FormattedValue) -> None:
        self.visit(node.value)


def check_sns_depth(node: ast.AST, limit: int = 1) -> bool:
    d = SinSDetector(limit)
    try:
        d.visit(node)
    except StringEmbeddingTooDeep:
        return False
    else:
        return True
