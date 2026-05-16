"""Fixture module for agent contract tests."""

from src.utils.helper import helper


def main() -> str:
    """Return the fixture greeting."""
    return helper()


if __name__ == "__main__":
    print(main())
