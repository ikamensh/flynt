raise NoAppException(
            'Detected multiple Flask applications in module "{}". Use '
            '"FLASK_APP={}:name" to specify the correct '
            'one.'.format(var1, var2)
        )