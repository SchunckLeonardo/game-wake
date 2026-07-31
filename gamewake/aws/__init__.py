"""AWS implementations of GameWake's external infrastructure contracts."""

from .ec2_runtime import Ec2RuntimeProvider

__all__ = ["Ec2RuntimeProvider"]
