import ast

with open("ast_example.py", "r") as source:
    tree = ast.parse(source.read())
    # print(type(tree))


def ast_repr(obj):
    ugly = str(obj)
    front = ugly.split()[0]
    return front.replace('<_ast.', '')

def recursive_visit(obj, depth):
    try:
        for e in obj:
            recursive_visit(e, depth)
        return
    except TypeError:
        if '_ast' in str(obj):
            print("    "*depth, ast_repr(obj))
            try:
                for v in obj.__dict__.values():
                    recursive_visit(v, depth + 1)
            except:
                pass





def traverse_tree(tree):
    body = tree.body
    for upper_level in body:
        recursive_visit(upper_level, 0)

traverse_tree(tree)





