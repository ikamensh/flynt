class FlyntException(Exception):
    pass


class ConversionRefused(FlyntException):
    pass


class StringEmbeddingTooDeep(FlyntException):
    pass
