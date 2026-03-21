#!/usr/bin/env python3
"""
PDF Enhance - PDF post-processing
Add headers/footers/covers to PDFs using PyMuPDF (fitz)

Usage:
    python enhance_pdf.py input.pdf                     # basic (headers/footers only)
    python enhance_pdf.py input.pdf -o output.pdf       # specify output file
    python enhance_pdf.py input.pdf --cover "Title" "Subtitle"  # add cover
    python enhance_pdf.py input.pdf --cover-only "Title" "Subtitle"  # create cover only
"""

import argparse
import sys
from pathlib import Path
from datetime import datetime

try:
    import fitz  # PyMuPDF
except ImportError:
    print("PyMuPDF is not installed.")
    print("Install: pip install PyMuPDF")
    sys.exit(1)


# Brand color (RGB 0-1 range)
INDIGO = (99/255, 102/255, 241/255)
INDIGO_DARK = (79/255, 70/255, 229/255)
TEXT_PRIMARY = (31/255, 41/255, 55/255)
TEXT_SECONDARY = (107/255, 114/255, 128/255)
WHITE = (1, 1, 1)

# Font search paths (macOS / Linux)
FONT_SEARCH_PATHS = [
    Path.home() / "Library/Fonts",
    Path("/System/Library/Fonts"),
    Path("/Library/Fonts"),
    Path("/usr/share/fonts"),
    Path("/usr/local/share/fonts"),
    Path.home() / ".fonts",
    Path.home() / ".local/share/fonts",
]


def find_font(name: str) -> str:
    """Dynamically search for font files on the system"""
    for search_dir in FONT_SEARCH_PATHS:
        font_path = search_dir / name
        if font_path.exists():
            return str(font_path)
        if search_dir.exists():
            matches = list(search_dir.rglob(name))
            if matches:
                return str(matches[0])
    raise FileNotFoundError(f"Font not found: {name}")


# Pretendard font path (dynamic search)
try:
    FONT_REGULAR = find_font("Pretendard-Regular.otf")
    FONT_BOLD = find_font("Pretendard-Bold.otf")
    FONT_SEMIBOLD = find_font("Pretendard-SemiBold.otf")
except FileNotFoundError as e:
    print(f"WARNING: {e}")
    print("Falling back to the default font.")
    FONT_REGULAR = None
    FONT_BOLD = None
    FONT_SEMIBOLD = None

# Design constants
HEADER_HEIGHT = 40
FOOTER_HEIGHT = 30
PAGE_MARGIN = 50


def load_fonts():
    """Load Pretendard font"""
    fonts = {}

    try:
        if FONT_REGULAR and FONT_BOLD and FONT_SEMIBOLD:
            fonts['regular'] = fitz.Font(fontfile=FONT_REGULAR)
            fonts['bold'] = fitz.Font(fontfile=FONT_BOLD)
            fonts['semibold'] = fitz.Font(fontfile=FONT_SEMIBOLD)
        else:
            raise FileNotFoundError("Pretendard font not found")
    except Exception as e:
        print(f"Font load failed: {e}")
        print("Using default font.")
        fonts['regular'] = fitz.Font("helv")
        fonts['bold'] = fitz.Font("hebo")
        fonts['semibold'] = fitz.Font("hebo")

    return fonts


def create_cover_page(title: str, subtitle: str = "", fonts: dict = None) -> fitz.Document:
    """Create a professional cover"""
    if fonts is None:
        fonts = load_fonts()

    doc = fitz.open()
    page = doc.new_page(width=595, height=842)  # A4 size
    rect = page.rect

    # Background: Indigo gradient effect (implemented as solid color)
    page.draw_rect(rect, color=None, fill=INDIGO)

    # Top decorative line
    top_line_rect = fitz.Rect(0, 80, rect.width, 82)
    page.draw_rect(top_line_rect, color=None, fill=WHITE)

    # Company logo text (top)
    tw_logo = fitz.TextWriter(rect)
    tw_logo.append((PAGE_MARGIN, 140), "Your Organization", font=fonts['bold'], fontsize=48)
    tw_logo.write_text(page, color=WHITE)

    # Company subtitle (below logo)
    tw_company = fitz.TextWriter(rect)
    tw_company.append((PAGE_MARGIN, 175), "Your Organization", font=fonts['regular'], fontsize=18)
    tw_company.write_text(page, color=WHITE)

    # Center divider line
    mid_y = 280
    mid_line_rect = fitz.Rect(PAGE_MARGIN, mid_y, rect.width - PAGE_MARGIN, mid_y + 2)
    page.draw_rect(mid_line_rect, color=None, fill=(1, 1, 1, 0.3))

    # Title (center)
    title_y = 380
    tw_title = fitz.TextWriter(rect)

    # Long title handling (max 20 chars per line)
    if len(title) > 20:
        # Insert line breaks at suitable positions
        mid = len(title) // 2
        # Find whitespace
        space_pos = title.rfind(' ', 0, mid + 5)
        if space_pos == -1:
            space_pos = mid

        title_line1 = title[:space_pos].strip()
        title_line2 = title[space_pos:].strip()

        tw_title.append((PAGE_MARGIN, title_y), title_line1, font=fonts['bold'], fontsize=32)
        tw_title.append((PAGE_MARGIN, title_y + 45), title_line2, font=fonts['bold'], fontsize=32)
    else:
        tw_title.append((PAGE_MARGIN, title_y), title, font=fonts['bold'], fontsize=36)

    tw_title.write_text(page, color=WHITE)

    # Subtitle
    if subtitle:
        subtitle_y = title_y + 100 if len(title) > 20 else title_y + 60
        tw_subtitle = fitz.TextWriter(rect)
        tw_subtitle.append((PAGE_MARGIN, subtitle_y), subtitle, font=fonts['regular'], fontsize=20)
        tw_subtitle.write_text(page, color=WHITE)

    # Bottom info
    bottom_y = rect.height - 120

    # Submission date
    today = datetime.now().strftime("%Y-%m")
    tw_date = fitz.TextWriter(rect)
    tw_date.append((PAGE_MARGIN, bottom_y), f"Submission date: {today}", font=fonts['regular'], fontsize=12)
    tw_date.write_text(page, color=WHITE)

    # Submitted by
    tw_author = fitz.TextWriter(rect)
    tw_author.append((PAGE_MARGIN, bottom_y + 22), "Submitted by: Your Organization", font=fonts['regular'], fontsize=12)
    tw_author.write_text(page, color=WHITE)

    # Bottom decorative line
    bottom_line_rect = fitz.Rect(0, rect.height - 40, rect.width, rect.height - 38)
    page.draw_rect(bottom_line_rect, color=None, fill=WHITE)

    return doc


def add_header_footer(
    input_path: str,
    output_path: str,
    skip_first_page: bool = True,
    header_text: str = "Your Organization",
    footer_url: str = "example.com"
):
    """Add headers and footers to a PDF"""
    fonts = load_fonts()
    doc = fitz.open(input_path)

    for page_num, page in enumerate(doc):
        rect = page.rect

        # Option to skip first page
        if skip_first_page and page_num == 0:
            continue

        # Header background (Indigo)
        header_rect = fitz.Rect(0, 0, rect.width, HEADER_HEIGHT)
        page.draw_rect(header_rect, color=None, fill=INDIGO)

        # Header text: Company (bold)
        tw_header = fitz.TextWriter(rect)
        tw_header.append((20, 26), "Company", font=fonts['bold'], fontsize=14)
        tw_header.write_text(page, color=WHITE)

        # Header text: Your Organization
        tw_company = fitz.TextWriter(rect)
        tw_company.append((58, 26), "Your Organization", font=fonts['regular'], fontsize=10)
        tw_company.write_text(page, color=WHITE)

        # Footer background (light gray)
        footer_rect = fitz.Rect(0, rect.height - FOOTER_HEIGHT, rect.width, rect.height)
        page.draw_rect(footer_rect, color=None, fill=(0.98, 0.98, 0.98))

        # Footer: page number (center)
        page_text = f"{page_num + 1}"
        tw_page = fitz.TextWriter(rect)
        # Rough calculation for centering
        tw_page.append((rect.width / 2 - 5, rect.height - 12), page_text, font=fonts['regular'], fontsize=10)
        tw_page.write_text(page, color=TEXT_SECONDARY)

        # Footer: URL (right)
        tw_url = fitz.TextWriter(rect)
        tw_url.append((rect.width - 70, rect.height - 12), footer_url, font=fonts['regular'], fontsize=9)
        tw_url.write_text(page, color=INDIGO)

    doc.save(output_path)
    doc.close()

    return output_path


def enhance_pdf(
    input_path: str,
    output_path: str = None,
    add_cover: bool = False,
    cover_title: str = "",
    cover_subtitle: str = "",
    skip_header_first: bool = True
):
    """Enhance the entire PDF"""
    input_file = Path(input_path)

    if output_path is None:
        output_path = str(input_file.with_stem(f"{input_file.stem}_enhanced"))

    fonts = load_fonts()

    # Create cover
    if add_cover and cover_title:
        cover_doc = create_cover_page(cover_title, cover_subtitle, fonts)

        # Open original PDF
        main_doc = fitz.open(input_path)

        # Insert body after cover
        cover_doc.insert_pdf(main_doc)

        # Temporary save
        temp_path = str(input_file.with_stem(f"{input_file.stem}_temp"))
        cover_doc.save(temp_path)
        cover_doc.close()
        main_doc.close()

        # Add headers/footers (exclude cover)
        add_header_footer(
            temp_path,
            output_path,
            skip_first_page=True,
            header_text="Your Organization",
            footer_url="example.com"
        )

        # Delete temporary file
        Path(temp_path).unlink()
    else:
        # Add headers/footers only
        add_header_footer(
            input_path,
            output_path,
            skip_first_page=skip_header_first,
            header_text="Your Organization",
            footer_url="example.com"
        )

    return output_path


def main():
    parser = argparse.ArgumentParser(
        description='PDF post-processing (headers/footers/cover)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s input.pdf                          # add headers/footers
  %(prog)s input.pdf -o output.pdf            # specify output file
  %(prog)s input.pdf --cover "Proposal Title"       # cover + headers/footers
  %(prog)s input.pdf --cover "Title" "Subtitle"     # cover (includes subtitle)
  %(prog)s --cover-only "Title" -o cover.pdf    # create cover only
        """
    )

    parser.add_argument('input', nargs='?', help='Input PDF file')
    parser.add_argument('-o', '--output', help='Output file path')
    parser.add_argument('--cover', nargs='+', metavar=('TITLE', 'SUBTITLE'),
                        help='Add a cover (title [subtitle])')
    parser.add_argument('--cover-only', nargs='+', metavar=('TITLE', 'SUBTITLE'),
                        help='Create cover only (title [subtitle])')
    parser.add_argument('--no-skip-first', action='store_true',
                        help='Add headers/footers to the first page as well')

    args = parser.parse_args()

    # create cover only
    if args.cover_only:
        title = args.cover_only[0]
        subtitle = args.cover_only[1] if len(args.cover_only) > 1 else ""
        output = args.output or "cover.pdf"

        fonts = load_fonts()
        cover_doc = create_cover_page(title, subtitle, fonts)
        cover_doc.save(output)
        cover_doc.close()

        print(f"Cover created: {output}")
        return

    # Input file required
    if not args.input:
        parser.error("Please specify an input PDF file.")

    if not Path(args.input).exists():
        print(f"File not found: {args.input}")
        sys.exit(1)

    # PDF processing
    add_cover = bool(args.cover)
    cover_title = args.cover[0] if args.cover else ""
    cover_subtitle = args.cover[1] if args.cover and len(args.cover) > 1 else ""

    output_path = enhance_pdf(
        args.input,
        args.output,
        add_cover=add_cover,
        cover_title=cover_title,
        cover_subtitle=cover_subtitle,
        skip_header_first=not args.no_skip_first
    )

    print(f"PDF processing complete: {output_path}")


if __name__ == '__main__':
    main()
