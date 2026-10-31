"""Clown Prophecy (Experimental): Clown Prophecy Sampler, Clown Prophecy Prompt, Clown Anchoring and Clown Carryover,
moved out of Clown Context Suite. Needs Clown Context Suite installed for Clown Context, Clown Shot Counter and Clown Chain."""
from .nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS
from .clown_carryover import NODE_CLASS_MAPPINGS as _CARRY_NODES, NODE_DISPLAY_NAME_MAPPINGS as _CARRY_NAMES

NODE_CLASS_MAPPINGS = {**NODE_CLASS_MAPPINGS, **_CARRY_NODES}
NODE_DISPLAY_NAME_MAPPINGS = {**NODE_DISPLAY_NAME_MAPPINGS, **_CARRY_NAMES}

WEB_DIRECTORY = "./web"
__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
