"""Typed exceptions. Every failure mode the pipeline can hit has a name."""

from __future__ import annotations


class FlyerError(Exception):
    """Base class for every error this application raises deliberately."""


class ConfigurationError(FlyerError):
    """Missing or invalid environment / configuration."""


class ClientError(FlyerError):
    """A client profile is missing, malformed or internally inconsistent."""


class AssetError(FlyerError):
    """An image asset is missing, unreadable or unusable."""


class ReferenceError(FlyerError):
    """A design reference is missing or has invalid metadata."""


class AIError(FlyerError):
    """Claude call failed, or returned something the schema rejects."""


class RenderError(FlyerError):
    """The renderer could not produce a valid flyer."""


class QAFailure(FlyerError):
    """A rendered flyer failed quality control."""


class DriveError(FlyerError):
    """Google Drive authentication or upload failed."""
