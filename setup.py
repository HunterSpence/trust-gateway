"""Setup script for Trust Gateway SDK"""
from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="trust-gateway-sdk",
    version="0.1.0",
    author="Hunter Spence",
    author_email="hspence21190@gmail.com",
    description="Python SDK for Trust Gateway - AI Agent Trust Scoring and Authorization",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://trust-gateway.dev",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Security",
        "License :: Other/Proprietary License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.8",
    install_requires=[
        "requests>=2.28.0",
    ],
)
