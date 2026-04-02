import json
import sys
import os
from io import BytesIO

from pypdf import PdfReader, PdfWriter, PdfMerger, Transformation
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import HexColor


import platform

def get_system_fonts_dir():
    system = platform.system()
    if system == "Windows":
        return os.path.join(os.environ.get("SystemRoot", "C:\\Windows"), "Fonts")
    elif system == "Darwin":
        return "/System/Library/Fonts"
    else:
        return "/usr/share/fonts"

FONTS_DIR = get_system_fonts_dir()

CHINESE_FONTS = {
    "simsun": ("simsun.ttc", 0),
    "simhei": ("simhei.ttf", None),
    "microsoftyahei": ("msyh.ttc", 0),
    "kaiti": ("simkai.ttf", None),
    "fangsong": ("simfang.ttf", None),
    "dengxian": ("dengxian.ttf", None),
}

_registered_fonts = set()

def register_chinese_font(font_name):
    if font_name.lower() in _registered_fonts:
        return font_name.lower()
    
    font_lower = font_name.lower()
    if font_lower in CHINESE_FONTS:
        font_info = CHINESE_FONTS[font_lower]
        font_filename = font_info[0]
        subfont_index = font_info[1]
        font_path = os.path.join(FONTS_DIR, font_filename)
        
        if os.path.exists(font_path):
            try:
                if subfont_index is not None:
                    pdfmetrics.registerFont(TTFont(font_lower, font_path, subfontIndex=subfont_index))
                else:
                    pdfmetrics.registerFont(TTFont(font_lower, font_path))
                _registered_fonts.add(font_lower)
                return font_lower
            except Exception as e:
                pass
    
    for name, font_info in CHINESE_FONTS.items():
        font_filename = font_info[0]
        subfont_index = font_info[1]
        font_path = os.path.join(FONTS_DIR, font_filename)
        
        if os.path.exists(font_path):
            try:
                if subfont_index is not None:
                    pdfmetrics.registerFont(TTFont(name, font_path, subfontIndex=subfont_index))
                else:
                    pdfmetrics.registerFont(TTFont(name, font_path))
                _registered_fonts.add(name)
                return name
            except Exception:
                continue
    
    return None


def contains_chinese(text):
    for char in text:
        if '\u4e00' <= char <= '\u9fff':
            return True
    return False


def transform_from_image_coords(bbox, image_width, image_height, pdf_width, pdf_height):
    x_scale = pdf_width / image_width
    y_scale = pdf_height / image_height

    left = bbox[0] * x_scale
    right = bbox[2] * x_scale

    top = pdf_height - (bbox[1] * y_scale)
    bottom = pdf_height - (bbox[3] * y_scale)

    return left, bottom, right, top


def transform_from_pdf_coords(bbox, pdf_height):
    left = bbox[0]
    right = bbox[2]

    pypdf_top = pdf_height - bbox[1]      
    pypdf_bottom = pdf_height - bbox[3]   

    return left, pypdf_bottom, right, pypdf_top


def create_text_overlay_pdf(page_width, page_height, text_items):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=(page_width, page_height))
    
    for item in text_items:
        text = item["text"]
        x = item["x"]
        y = item["y"]
        font_size = item.get("font_size", 14)
        font_name = item.get("font_name", "simsun")
        font_color = item.get("font_color", "000000")
        
        if contains_chinese(text):
            registered_font = register_chinese_font(font_name)
            if registered_font:
                c.setFont(registered_font, font_size)
            else:
                c.setFont("Helvetica", font_size)
        else:
            c.setFont("Helvetica", font_size)
        
        try:
            color = HexColor(f"#{font_color}")
        except Exception:
            color = HexColor("#000000")
        c.setFillColor(color)
        
        c.drawString(x, y, text)
    
    c.save()
    buffer.seek(0)
    return buffer


def fill_pdf_form(input_pdf_path, fields_json_path, output_pdf_path):
    
    with open(fields_json_path, "r", encoding="utf-8") as f:
        fields_data = json.load(f)
    
    reader = PdfReader(input_pdf_path)
    
    pdf_dimensions = {}
    for i, page in enumerate(reader.pages):
        mediabox = page.mediabox
        pdf_dimensions[i + 1] = [float(mediabox.width), float(mediabox.height)]
    
    text_items_by_page = {}
    
    for field in fields_data["form_fields"]:
        page_num = field["page_number"]

        page_info = next(p for p in fields_data["pages"] if p["page_number"] == page_num)
        pdf_width, pdf_height = pdf_dimensions[page_num]

        if "pdf_width" in page_info:
            left, bottom, right, top = transform_from_pdf_coords(
                field["entry_bounding_box"],
                pdf_height
            )
        else:
            image_width = page_info["image_width"]
            image_height = page_info["image_height"]
            left, bottom, right, top = transform_from_image_coords(
                field["entry_bounding_box"],
                image_width, image_height,
                pdf_width, pdf_height
            )
        
        if "entry_text" not in field or "text" not in field["entry_text"]:
            continue
        entry_text = field["entry_text"]
        text = entry_text["text"]
        if not text:
            continue
        
        font_name = entry_text.get("font", "simsun")
        font_size = entry_text.get("font_size", 14)
        font_color = entry_text.get("font_color", "000000")
        
        text_y = bottom + (top - bottom - font_size) / 2 + font_size * 0.2
        
        if page_num not in text_items_by_page:
            text_items_by_page[page_num] = []
        
        text_items_by_page[page_num].append({
            "text": text,
            "x": left,
            "y": text_y,
            "font_size": font_size,
            "font_name": font_name,
            "font_color": font_color
        })
    
    writer = PdfWriter()
    writer.append(reader)
    
    for page_num, text_items in text_items_by_page.items():
        pdf_width, pdf_height = pdf_dimensions[page_num]
        
        overlay_buffer = create_text_overlay_pdf(pdf_width, pdf_height, text_items)
        overlay_reader = PdfReader(overlay_buffer)
        overlay_page = overlay_reader.pages[0]
        
        writer_page = writer.pages[page_num - 1]
        writer_page.merge_page(overlay_page)
    
    with open(output_pdf_path, "wb") as output:
        writer.write(output)
    
    total_annotations = sum(len(items) for items in text_items_by_page.values())
    print(f"Successfully filled PDF form and saved to {output_pdf_path}")
    print(f"Added {total_annotations} text annotations")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: fill_pdf_form_with_annotations.py [input pdf] [fields.json] [output pdf]")
        sys.exit(1)
    input_pdf = sys.argv[1]
    fields_json = sys.argv[2]
    output_pdf = sys.argv[3]
    
    fill_pdf_form(input_pdf, fields_json, output_pdf)
