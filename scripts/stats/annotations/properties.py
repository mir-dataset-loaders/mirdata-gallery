"""Which track properties of a dataset are official mirdata annotations, and of which type."""

import mirdata

from card_fields import _annotation_class_name
from stats.annotations.types import ANNOTATION_TYPES


def annotation_properties(ds):
    """{property name: annotation type} for the dataset's Track class.

    Uses the same detection as the card's "annotations" field, restricted to
    the official mirdata annotation types.
    """
    found = {}
    track_class = getattr(ds, "_track_class", None)
    for attr in dir(track_class):
        if attr.startswith("_"):
            continue
        item = getattr(track_class, attr, None)
        if isinstance(item, (property, mirdata.core.cached_property)):
            ann_cls = _annotation_class_name(attr, item)
            if ann_cls in ANNOTATION_TYPES:
                found[attr] = ann_cls
    return found
