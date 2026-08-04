"""Pure validation algorithms for Italian synthetic identifiers."""

from __future__ import annotations


CF_ODD_VALUES = {
    **dict(zip("0123456789", (1, 0, 5, 7, 9, 13, 15, 17, 19, 21))),
    **dict(zip("ABCDEFGHIJKLMNOPQRSTUVWXYZ", (1, 0, 5, 7, 9, 13, 15, 17, 19, 21, 2, 4, 18, 20, 11, 3, 6, 8, 12, 14, 16, 10, 22, 25, 24, 23))),
}
CF_MONTH_CODES = "ABCDEHLMPRST"


def tax_code_check_character(first_fifteen: str) -> str:
    if len(first_fifteen) != 15:
        raise ValueError("A tax-code payload must contain 15 characters")
    total = 0
    for position, character in enumerate(first_fifteen, start=1):
        if position % 2:
            total += CF_ODD_VALUES[character]
        else:
            total += int(character) if character.isdigit() else ord(character) - 65
    return chr(65 + total % 26)


def is_valid_tax_code(value: str) -> bool:
    if len(value) != 16 or not value.isalnum() or value != value.upper():
        return False
    try:
        return tax_code_check_character(value[:15]) == value[-1]
    except (KeyError, ValueError):
        return False


def iban_mod97(value: str) -> int:
    numeric = "".join(str(ord(char) - 55) if char.isalpha() else char for char in value)
    remainder = 0
    for character in numeric:
        remainder = (remainder * 10 + int(character)) % 97
    return remainder


def is_valid_italian_iban(value: str) -> bool:
    return (
        len(value) == 27
        and value.startswith("IT")
        and value[2:].isalnum()
        and iban_mod97(value[4:] + value[:4]) == 1
    )
