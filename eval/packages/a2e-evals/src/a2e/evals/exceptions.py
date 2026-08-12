class A2EException(Exception):
    pass


class A2EContextLimitExceeded(A2EException):
    pass


class A2ETemplateMappingError(A2EException):
    pass


class A2EUnsupportedAudioFormat(A2EException):
    pass


class A2EUnsupportedImageFormat(A2EException):
    pass
