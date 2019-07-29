import datetime

def a():
    test = 'Test'
    return f"{test} ({datetime.datetime.now():%B %d, %Y})"