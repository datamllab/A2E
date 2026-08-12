class A2EException(Exception):
    pass


class A2EEvaluationNameIsMissing(A2EException):
    pass


class A2EMigrationError(A2EException):
    pass
