"""Turn a slide PDF into square images and a PowerPoint deck with speaker notes.

    from research_helpers.carousel import pdf_to_images, images_to_pptx

    images = pdf_to_images("slides.pdf", "out/images", pixels=1440)
    images_to_pptx(images, "slides.pptx", notes=["Read this aloud.", ...])

Needs pdftoppm (from Poppler) on the path. images_to_pptx needs python-pptx. Each deck page is one full-slide picture, so it looks exactly
like the PDF. PNG suits slides of text: it keeps edges sharp, and social platforms recompress uploads themselves.
"""
import pathlib
import subprocess


def pdf_to_images(pdf, out_dir, pixels=1440, prefix="slide"):
    """Render each page to PNG with its long side set to `pixels`. Returns the file paths in page order."""
    out = pathlib.Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    subprocess.run(["pdftoppm", "-png", "-scale-to", str(pixels), str(pdf), str(out / prefix)], check=True)
    return sorted(out.glob(f"{prefix}-*.png"))


def images_to_pptx(images, pptx, notes=None):
    """Make a deck with one full-slide picture per image, and optional speaker notes per slide."""
    from pptx import Presentation
    from pptx.util import Emu

    images = list(images)
    notes = list(notes or [])
    if notes and len(notes) != len(images):
        raise ValueError(f"{len(images)} images but {len(notes)} notes")
    deck = Presentation()
    deck.slide_width = deck.slide_height = Emu(6858000)
    blank = deck.slide_layouts[6]
    for i, image in enumerate(images):
        slide = deck.slides.add_slide(blank)
        slide.shapes.add_picture(str(image), 0, 0, deck.slide_width, deck.slide_height)
        if notes:
            slide.notes_slide.notes_text_frame.text = notes[i]
    deck.save(str(pptx))
    return pathlib.Path(pptx)
