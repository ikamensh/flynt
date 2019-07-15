raise NoAppException(
            f'Detected multiple Flask applications in module "{var1}". Use "FLASK_APP={var2}:name" to specify the correct one.'
        )