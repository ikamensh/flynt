raise NoAppException(
            'Detected multiple Flask applications in module "{module}". Use '
            '"FLASK_APP={module}:name" to specify the correct '
            'one.'.format(module=module.__name__)
        )