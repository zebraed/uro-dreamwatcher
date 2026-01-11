# -*- coding: utf-8 -*-

class SecretStr(str):
    def __repr__(self) -> str:
        return "<secret>"
