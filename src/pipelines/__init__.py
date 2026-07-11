"""Trusted shared and user pipeline modules.

Entry points are intentionally not imported eagerly: importing the user worker
path must never import Connector implementations as a package side effect.
"""
