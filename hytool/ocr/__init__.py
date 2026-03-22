"""Compatibility wrapper exposing the ocr package as hytool.ocr."""

from hytool._alias import alias_package

alias_package(__name__, "ocr")