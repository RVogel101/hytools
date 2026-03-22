#!/usr/bin/env python3
"""Setup configuration for armenian-corpus-core package."""

from setuptools import setup, find_packages

setup(
    name="hytool",
    version="0.1.0-alpha",
    packages=find_packages(),
    python_requires=">=3.10",
    description="Central package for Armenian language corpus contracts, extraction, and normalization",
    long_description=open("README.md", encoding="utf-8").read() if __name__ == "__main__" else "",
    author="Armenian Corpus Core Contributors",
    url="https://github.com/RVogel101/armenian-corpus-core",
    license="MIT",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
)
