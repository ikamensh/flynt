d = {"something": "what"}

resp = """
%(something)s
""" % d

print(resp)
