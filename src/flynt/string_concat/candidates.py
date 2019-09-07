import ast


def is_str_literal(node):
    """ Returns True if a node is a string literal """
    if isinstance(node, ast.Constant):
        return isinstance(node.value, str)
    else:
        return False


def is_str_compatible(node):
    """ Returns False if any nodes can't be a part of string concatenation """
    if is_str_literal(node):
        return True
    if isinstance(node, ast.BinOp):
        if not isinstance(node.op, ast.Add):
            return False
        else:
            return is_str_compatible(node.right) and is_str_compatible(node.left)
    elif isinstance(node, ast.Name):
        return True
    else:
        return False


def contains_literal(node):
    """ Returns true if a node or its BinOp children are string literals """
    if is_str_literal(node):
        return True
    elif isinstance(node, ast.BinOp):
        return contains_literal(node.left) or contains_literal(node.right)


def is_string_concat(node):
    """ Returns True for nodes representing a string concatenation """
    if not is_str_compatible(node):
        return False
    if not isinstance(node, ast.BinOp):
        return False
    return contains_literal(node)


class ConcatHound(ast.NodeVisitor):
    def __init__(self):
        super().__init__()
        self.victims = []

    def visit_BinOp(self, node: ast.BinOp):
        """
        Finds all nodes that are string concatenations with a literal
        """
        if is_string_concat(node):
            self.victims.append(node)
