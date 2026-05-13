"""
Types for the dreamwatcher project.
"""


class SecretStr(str):
    """
    Secret string type.
    """
    def __repr__(self) -> str:
        return "<secret>"
