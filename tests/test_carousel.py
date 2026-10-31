"""The deck must hold one picture and one set of notes per image."""
import pytest

pptx = pytest.importorskip("pptx")
from research_helpers.carousel import images_to_pptx

PNG = bytes.fromhex("89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d49444154789c6360000002000001e221bc330000000049454e44ae426082")


def test_deck_has_notes(tmp_path):
    images = []
    for i in range(2):
        p = tmp_path / f"s{i}.png"
        p.write_bytes(PNG)
        images.append(p)
    deck = images_to_pptx(images, tmp_path / "d.pptx", ["one", "two"])
    read = pptx.Presentation(str(deck))
    assert [s.notes_slide.notes_text_frame.text for s in read.slides] == ["one", "two"]


def test_mismatch_is_refused(tmp_path):
    p = tmp_path / "s.png"
    p.write_bytes(PNG)
    with pytest.raises(ValueError):
        images_to_pptx([p], tmp_path / "d.pptx", ["one", "two"])
