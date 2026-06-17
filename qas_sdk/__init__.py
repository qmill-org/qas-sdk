"""
QAS SDK - Python client for QAS Circuit Compression API

A Python library for interacting with the QAS platform for quantum circuit
compression using LUMI supercomputer and AWS Braket quantum devices.
"""

__version__ = "0.1.4"

from .client import (
    CompressionJobOptions,
    QASAPIError,
    QASAuthError,
    QASClient,
    compress_and_wait,
)

__all__ = [
    "CompressionJobOptions",
    "QASAPIError",
    "QASAuthError",
    "QASClient",
    "__version__",
    "compress_and_wait",
]
