import ast

with open("ast_example.py", "r") as source:
    tree = ast.parse(source.read())
    # print(type(tree))


def ast_repr(obj):
    ugly = str(obj)
    front = ugly.split()[0]
    return front.replace('<_ast.', '')

from dev.create_fstring import matching_call, f_stringify

def recursive_visit(obj, depth):
    try:
        for e in obj:
            recursive_visit(e, depth)
        return
    except TypeError:
        if '_ast' in str(obj):
            print("    "*depth, ast_repr(obj))
            attr_names = obj._fields
            for name in attr_names:
                attr = getattr(obj, name)
                if matching_call(attr):
                    attr = f_stringify(attr)
                    setattr(obj, name, attr)
                if isinstance(attr, str): return
                recursive_visit(attr, depth + 1)




if __name__ == "__main__":
    def traverse_tree(tree):
        body = tree.body
        for upper_level in body:
            recursive_visit(upper_level, 0)

    traverse_tree(tree)





