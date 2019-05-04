from flint.mutator import matching_call, f_stringify

def recursive_visit(obj, depth):
    """
    traverse ast recursively, replacing
    string format calls with f-string literals.
    """
    try:
        for e in obj:
            recursive_visit(e, depth)
        return
    except TypeError:
        if '_ast' in str(obj):
            attr_names = obj._fields
            for name in attr_names:
                attr = getattr(obj, name)
                if matching_call(attr):
                    attr = f_stringify(attr)
                    setattr(obj, name, attr)
                if isinstance(attr, str): return
                recursive_visit(attr, depth + 1)









