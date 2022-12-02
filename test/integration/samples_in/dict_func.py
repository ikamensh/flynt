import datetime


def a():
    test = 'Test'
    return "{name} ({date:%B %d, %Y})".format( name=test, date=datetime.datetime.now() )
