# -*- coding: utf-8 -*-

class SecretStr(str):
    def __repr__(self) -> str:
        return "<secret>"

    def __str__(self) -> str:
        return "<secret>"
