class SecretStr(str):
    def __repr__(self) -> str:
        return "<secret>"
