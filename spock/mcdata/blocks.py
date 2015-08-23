from minecraft_data.v1_8 import blocksArray

from spock.utils import BoundingBox, create_namedtuple

blocks = {}
_replace = {"displayName": "display_name",
            "boundingBox": "bounding_box",
            "harvestTools": "harvest_tools",
            "stackSize": "stack_size"}


def get_boundingbox(bb):
    if bb == "block":
        return BoundingBox(1, 1)
    elif bb == "empty":
        return None


def _create_blocks():
    for block in blocksArray:
        if "boundingBox" in block:
            block["boundingBox"] = get_boundingbox(block["boundingBox"])
        if "harvestTools" in block:
            block["harvestTools"] = tuple(block["harvestTools"].keys())
        blocks[block['id']] = create_namedtuple(block, replacements=_replace,
                                                name=block["name"])


_create_blocks()


def get_block(block_id, meta=0):
        return blocks[block_id] if block_id < len(blocks) else None
