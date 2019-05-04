from flint.transform import matching_call, f_stringify

def is_an_ast_node(x):
    return '_ast' in str(x)


def recursive_visit(node, depth: int):
    """
    traverse ast recursively, replacing
    string format calls with f-string literals.

    Keep track of the node depth, for print and debug purposes mainly.
    """

    count_transforms = 0

    # ignore strings
    if isinstance(node, str):
        return count_transforms

    try:
        # handle list / collection nodes
        for e in node:
            count_transforms += recursive_visit(e, depth)
    except TypeError:
        # current node is not a collection
        if is_an_ast_node(node):
            attr_names = node._fields
            for name in attr_names:
                attr = getattr(node, name)
                if matching_call(attr):
                    attr = f_stringify(attr)
                    setattr(node, name, attr)
                    count_transforms += 1
                    continue

                count_transforms += recursive_visit(attr, depth + 1)

    return count_transforms









