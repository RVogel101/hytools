"""Compatibility wrapper exposing the cleaning package as hytool.cleaning."""

from hytool._alias import alias_package

alias_package(__name__, "cleaning")