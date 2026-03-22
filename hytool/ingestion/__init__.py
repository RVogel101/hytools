"""Compatibility wrapper exposing the ingestion package as hytool.ingestion."""

from hytool._alias import alias_package

alias_package(__name__, "ingestion")