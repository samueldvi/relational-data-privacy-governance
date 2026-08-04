"""Compatibility shim for the infrastructure database adapter."""

from src.infrastructure.database.connection import get_connection

__all__ = ["get_connection"]
