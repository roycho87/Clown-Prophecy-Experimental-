"""Geiru Prophecy (Experimental): Geiru Prophecy Sampler, Geiru Prophecy Prompt and Clown Carryover,
moved out of Geiru Context Suite. Needs Geiru Context Suite installed for Geiru Context, Geiru Anchoring, Geiru Shot Counter and Geiru Chain."""
from .nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS
from .clown_carryover import NODE_CLASS_MAPPINGS as _CARRY_NODES, NODE_DISPLAY_NAME_MAPPINGS as _CARRY_NAMES

NODE_CLASS_MAPPINGS = {**NODE_CLASS_MAPPINGS, **_CARRY_NODES}
NODE_DISPLAY_NAME_MAPPINGS = {**NODE_DISPLAY_NAME_MAPPINGS, **_CARRY_NAMES}

WEB_DIRECTORY = "./web"
__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
