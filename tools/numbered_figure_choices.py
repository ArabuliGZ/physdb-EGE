"""Lossless source-page crops for tasks with five numbered picture choices.

Boxes omit the printed choice numbers; the site supplies consistent 1–5 labels.
The composite hash and size guard against silently cropping a different source.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO

from PIL import Image


@dataclass(frozen=True)
class ChoiceCrop:
    size: tuple[int, int]
    boxes: tuple[tuple[int, int, int, int], ...]


CHOICE_CROPS = {
    # ФИПИ 2027, demo task 20: three circuits on the left, two on the right.
    "eeb8e40c011340c8458157ef7ba3d6d397bb3959fbc34a9e4a772ce7f5e5ac2c": ChoiceCrop(
        (589, 380), ((32, 0, 185, 126), (32, 126, 185, 253),
                     (32, 253, 185, 380), (408, 0, 560, 126),
                     (408, 126, 560, 253))),
    # Демидова 2026-1, task 20. The 2026-4 task 20 has a data table instead.
    "a16c1726094157a3b63250bf69e257f426bddca41d47d142f8c7c0f2743b0a72": ChoiceCrop(
        (1456, 1056), ((96, 0, 460, 350), (96, 350, 460, 710),
                       (96, 710, 460, 1056), (1080, 0, 1456, 350),
                       (1080, 350, 1456, 710))),
    # Демидова 2025-1-2 and its 2025-2-2 duplicate, task 20.
    "eba09f250af76bb8dee66351f38dd6c21989194f5b4f13e9310b04f68c0b0e28": ChoiceCrop(
        (900, 940), ((72, 0, 320, 310), (72, 310, 320, 620),
                     (72, 620, 320, 940), (660, 0, 895, 310),
                     (660, 310, 895, 620))),
    # Демидова 2024-1-4, task 20.
    "6deb5bf63fc2cf9f9959265e4f90bfadcbf0e635e741ecf74b4107c65e5ea558": ChoiceCrop(
        (900, 885), ((55, 0, 275, 295), (55, 295, 275, 585),
                     (55, 585, 275, 885), (610, 0, 830, 295),
                     (610, 295, 830, 585))),
    # Демидова 2024-2-2, task 20.
    "cef46af407c88939eb27ace83141f9a96ee44f3150a007e97b91b9ca6755024f": ChoiceCrop(
        (900, 885), ((55, 0, 275, 295), (55, 295, 275, 585),
                     (55, 585, 275, 885), (610, 0, 830, 295),
                     (610, 295, 830, 585))),
}


def split_numbered_choices(composite: bytes) -> list[bytes]:
    digest = sha256(composite).hexdigest()
    spec = CHOICE_CROPS.get(digest)
    if spec is None:
        raise ValueError(f"Unrecognized five-choice composite: {digest}")
    with Image.open(BytesIO(composite)) as source:
        if source.size != spec.size:
            raise ValueError(f"Unexpected composite size for {digest}: {source.size}")
        parts = []
        for box in spec.boxes:
            output = BytesIO()
            source.crop(box).save(output, format="PNG")
            parts.append(output.getvalue())
    return parts
