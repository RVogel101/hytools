"""Compatibility wrapper exposing the integrations package as hytool.integrations."""

from hytool._alias import alias_package

alias_package(__name__, "integrations")