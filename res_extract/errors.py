from __future__ import annotations


class ParseError(ValueError):
    pass


class NotNEFile(ParseError):
    pass


class BadResourceTable(ParseError):
    pass
