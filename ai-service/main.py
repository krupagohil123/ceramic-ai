from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image
import pymupdf
import os
import io
import sys
import re
import hashlib
import logging
import shutil
import uuid
from typing import Any, Dict, List, Optional

# Ensure UTF-8 output on Windows consoles
try:
    if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass


# ============================================================
# APP
# ============================================================

app = FastAPI(
    title="Ceramic AI Service",
    version="5.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# ROOT & HEALTH
# ============================================================

@app.get("/")
def root():
    return {
        "success": True,
        "message": "Ceramic AI Python service is running",
        "version": "5.0.0"
    }


@app.get("/health")
def health():
    return {
        "success": True,
        "service": "ai-service",
        "status": "healthy",
        "version": "5.0.0"
    }


# ============================================================
# TEXT & FORMATTING UTILITIES
# ============================================================

def normalize_text(text: Any) -> str:
    if text is None:
        return ""
    text = str(text)
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\u00a0", " ")
    text = text.replace("ﬁ", "fi").replace("ﬂ", "fl")
    text = re.sub(r"[\u200b-\u200d\uFEFF\x08]", "", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def unique_list(values: Any) -> List[Any]:
    if values is None:
        return []
    if isinstance(values, str):
        values = [values]
    if not isinstance(values, list):
        return []
    seen = set()
    result = []
    for item in values:
        if item is not None and str(item).strip():
            clean_item = str(item).strip()
            if clean_item.lower() not in seen:
                seen.add(clean_item.lower())
                result.append(clean_item)
    return result


def clean_doc_name(filename: str) -> str:
    base = os.path.splitext(filename or "document")[0]
    return re.sub(r"[^a-zA-Z0-9_-]", "_", base)


# ============================================================
# CONSTANTS & REGEXES
# ============================================================

CODE_REGEX = re.compile(r"\b([A-Z0-9]{2,12}(?:[-/][A-Z0-9]{2,12})+)\b|\b([A-Z]{1,5}\d{3,10})\b", re.IGNORECASE)
CERTIFICATION_REGEX = re.compile(r"^(?:ISO|EN|ANSI|ASTM|BIS|IS|DIN|CE)[\s-]*\d", re.IGNORECASE)
SIZE_REGEX = re.compile(
    r"(?<![A-Z0-9])\d{2,4}\s*[x×X*]\s*\d{2,4}(?:\s*[x×X*]\s*\d{2,4})?\s*(?:mm|cm)?\b",
    re.IGNORECASE
)
PRODUCT_ROW_REGEX = re.compile(r"^(?:wall|floor)(?:\s*[-–]\s*\d+)?\s*(.*)$", re.IGNORECASE)

FINISH_MAP = {
    "chrome": "Chrome",
    "gun metal": "Gun Metal",
    "gunmetal": "Gun Metal",
    "rose gold": "Rose Gold",
    "rosegold": "Rose Gold",
    "matt black": "Matt Black",
    "matte black": "Matt Black",
    "french gold": "French Gold",
    "white": "White",
    "ivory": "Ivory",
    "black": "Black",
    "polished": "Polished",
    "matt": "Matt",
    "matte": "Matt",
    "glossy": "Glossy",
    "high gloss": "High Gloss",
    "satin": "Satin",
    "carving": "Carving",
    "rocker": "Rocker",
    "protect": "Protect",
    "sugar": "Sugar",
    "leather": "Leather",
}


# ============================================================
# IMAGE EXTRACTION & STORAGE
# ============================================================

def get_images_output_dir(safe_doc_name: str) -> str:
    service_dir = os.path.dirname(os.path.abspath(__file__))
    dir_path = os.path.join(service_dir, "extracted_images", safe_doc_name, "product_crops")
    os.makedirs(dir_path, exist_ok=True)
    return dir_path


def save_unique_image(image_bytes: bytes, output_dir: str, safe_doc_name: str, prefix: str, extension: str) -> str:
    extension = extension.lstrip(".")
    while True:
        image_name = f"{prefix}-{uuid.uuid4().hex}.{extension}"
        image_path = os.path.join(output_dir, image_name)
        try:
            descriptor = os.open(image_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        except FileExistsError:
            continue
        try:
            with os.fdopen(descriptor, "wb") as image_file:
                image_file.write(image_bytes)
        except Exception:
            try:
                os.remove(image_path)
            except OSError:
                pass
            raise
        return f"extracted_images/{safe_doc_name}/product_crops/{image_name}"


def save_image_from_xref(doc: pymupdf.Document, xref: int, output_dir: str, safe_doc_name: str, prefix: str) -> Optional[str]:
    try:
        base_img = doc.extract_image(xref)
        if not base_img:
            return None
        image_bytes = base_img.get("image")
        image_ext = base_img.get("ext", "png")
        if not image_bytes or len(image_bytes) < 300:
            return None

        # Verify image dimensions
        img = Image.open(io.BytesIO(image_bytes))
        width, height = img.size
        if width < 25 or height < 25:
            return None

        return save_unique_image(image_bytes, output_dir, safe_doc_name, prefix, image_ext)
    except Exception as e:
        return None


def crop_image_from_bbox(page: pymupdf.Page, bbox: List[float], output_dir: str, safe_doc_name: str, prefix: str, padding: float = 5.0) -> Optional[str]:
    try:
        crop_rect = pymupdf.Rect(bbox[0] - padding, bbox[1] - padding, bbox[2] + padding, bbox[3] + padding)
        if crop_rect.width < 25 or crop_rect.height < 25:
            return None

        pix = page.get_pixmap(
            matrix=pymupdf.Matrix(2.5, 2.5),
            clip=crop_rect,
            alpha=False
        )

        return save_unique_image(pix.tobytes("png"), output_dir, safe_doc_name, prefix, "png")
    except Exception as e:
        return None


def crop_image_from_xref(doc: pymupdf.Document, image: Dict[str, Any], bbox: tuple, output_dir: str, safe_doc_name: str, prefix: str) -> Optional[str]:
    try:
        transform = image.get("transform")
        if transform and (abs(transform[1]) > 0.001 or abs(transform[2]) > 0.001):
            return None
        source = doc.extract_image(image["xref"])
        source_image = Image.open(io.BytesIO(source["image"]))
        source_width, source_height = source_image.size
        image_bbox = image["bbox"]
        scale_x = source_width / (image_bbox[2] - image_bbox[0])
        scale_y = source_height / (image_bbox[3] - image_bbox[1])
        crop = (
            max(0, int((bbox[0] - image_bbox[0]) * scale_x)),
            max(0, int((bbox[1] - image_bbox[1]) * scale_y)),
            min(source_width, int((bbox[2] - image_bbox[0]) * scale_x)),
            min(source_height, int((bbox[3] - image_bbox[1]) * scale_y)),
        )
        if crop[2] - crop[0] < 25 or crop[3] - crop[1] < 25:
            return None
        isolated = source_image.crop(crop).convert("RGB")
        return save_unique_image(isolated.tobytes("png"), output_dir, safe_doc_name, prefix, "png")
    except Exception:
        return None


def image_distance_to_candidate(image_bbox: List[float], candidate_bbox: tuple) -> Optional[float]:
    horizontal_overlap = min(image_bbox[2], candidate_bbox[2]) - max(image_bbox[0], candidate_bbox[0])
    if horizontal_overlap <= 0:
        return None
    vertical_gap = max(
        0,
        image_bbox[1] - candidate_bbox[3],
        candidate_bbox[1] - image_bbox[3],
    )
    if vertical_gap > 180:
        return None
    return vertical_gap


def eligible_image_placements(page: pymupdf.Page, candidates: List[Dict[str, Any]], layout_lines: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    images = []
    page_area = page.rect.width * page.rect.height
    candidate_positions = {
        (round(candidate["bbox"][0] / 4), round(candidate["bbox"][1] / 4))
        for candidate in candidates
    }
    for image in page.get_image_info(xrefs=True):
        bbox = image.get("bbox")
        if not bbox:
            continue
        width = bbox[2] - bbox[0]
        height = bbox[3] - bbox[1]
        if width < 25 or height < 25:
            continue

        image_area = width * height
        aspect_ratio = width / height
        overlaps_product_text = any(
            min(bbox[2], candidate["bbox"][2]) > max(bbox[0], candidate["bbox"][0])
            and min(bbox[3], candidate["bbox"][3]) > max(bbox[1], candidate["bbox"][1])
            for candidate in candidates
        )
        if aspect_ratio >= 2.8 and overlaps_product_text and image_area < page_area * 0.02:
            continue

        broad = width >= page.rect.width * 0.9 or height >= page.rect.height * 0.9
        if broad:
            related_candidates = [
                candidate for candidate in candidates
                if image_distance_to_candidate(bbox, candidate["bbox"]) is not None
            ]
            if not related_candidates:
                continue

            fills_page = (
                image_area >= page_area * 0.85
                and bbox[0] <= page.rect.x0 + page.rect.width * 0.03
                and bbox[1] <= page.rect.y0 + page.rect.height * 0.03
                and bbox[2] >= page.rect.x1 - page.rect.width * 0.03
                and bbox[3] >= page.rect.y1 - page.rect.height * 0.03
            )
            if fills_page or (overlaps_product_text and image_area >= page_area * 0.5 and len(candidate_positions) < 2):
                continue
        images.append(image)
    return images


def aligned_image_cells(
    candidates: List[Dict[str, Any]],
    selected_images: List[Optional[int]],
    page_images: List[Dict[str, Any]],
    layout_lines: Optional[List[Dict[str, Any]]] = None,
) -> Dict[int, tuple]:
    cells = {}
    shared_indexes = {index for index in selected_images if index is not None}
    layout_anchors = []
    for line in layout_lines or []:
        if not re.match(r"^\s*(?:wall|floor|counter|table)\b", line["text"], re.IGNORECASE):
            continue
        anchor = {"bbox": tuple(line["bbox"]), "text": line["text"]}
        if not any(
            abs(anchor["bbox"][0] - existing["bbox"][0]) < 3
            and abs(anchor["bbox"][1] - existing["bbox"][1]) < 3
            for existing in layout_anchors
        ):
            layout_anchors.append(anchor)

    for image_index in shared_indexes:
        sibling_indexes = [index for index, selected in enumerate(selected_images) if selected == image_index]
        siblings = sorted(sibling_indexes, key=lambda index: candidates[index]["bbox"][0])
        image_bbox = page_images[image_index]["bbox"]
        relevant_anchors = []
        for anchor in layout_anchors:
            anchor_bbox = anchor["bbox"]
            if not (image_bbox[0] - 25 <= anchor_bbox[0] <= image_bbox[2] + 25):
                continue
            if not any(abs(anchor_bbox[1] - candidates[index]["bbox"][1]) <= 60 for index in siblings):
                continue
            associated = [
                index for index in range(len(candidates))
                if abs(candidates[index]["bbox"][0] - anchor_bbox[0]) <= 12
                and abs(candidates[index]["bbox"][1] - anchor_bbox[1]) <= 20
            ]
            if associated and not any(selected_images[index] == image_index for index in associated):
                continue
            relevant_anchors.append(anchor)

        if not relevant_anchors:
            relevant_anchors = [
                {"bbox": tuple(candidates[index]["bbox"]), "text": candidates[index].get("name") or ""}
                for index in siblings
            ]

        rows = []
        for anchor in sorted(relevant_anchors, key=lambda item: item["bbox"][1]):
            row = next((row for row in rows if abs(row[0]["bbox"][1] - anchor["bbox"][1]) <= 12), None)
            if row is None:
                rows.append([anchor])
            else:
                if not any(abs(anchor["bbox"][0] - item["bbox"][0]) < 3 for item in row):
                    row.append(anchor)

        for row in rows:
            row.sort(key=lambda item: item["bbox"][0])
            positions = [item["bbox"][0] for item in row]
            gaps = [right - left for left, right in zip(positions, positions[1:]) if right - left >= 25]
            typical_pitch = sorted(gaps)[len(gaps) // 2] if gaps else None
            for position, anchor in enumerate(row):
                anchor_x = anchor["bbox"][0]
                next_x = positions[position + 1] if position < len(positions) - 1 else None
                if next_x is not None:
                    left = image_bbox[0] if position == 0 and anchor_x - image_bbox[0] <= 45 else anchor_x
                    right = next_x
                else:
                    matching_candidate = min(
                        siblings,
                        key=lambda index: abs(candidates[index]["bbox"][0] - anchor_x)
                        + abs(candidates[index]["bbox"][1] - anchor["bbox"][1]),
                    )
                    candidate_bbox = candidates[matching_candidate]["bbox"]
                    estimated_width = min(180, max(80, candidate_bbox[2] - candidate_bbox[0] + 8))
                    pitch = typical_pitch or estimated_width
                    left = image_bbox[0] if position == 0 and anchor_x - image_bbox[0] <= 45 else anchor_x
                    right = min(image_bbox[2], anchor_x + max(estimated_width, pitch))
                left = max(left, image_bbox[0])
                right = min(right, image_bbox[2])
                if right - left < 25:
                    continue

                matching_indexes = [
                    index for index in siblings
                    if abs(candidates[index]["bbox"][0] - anchor_x) <= 12
                    and abs(candidates[index]["bbox"][1] - anchor["bbox"][1]) <= 20
                ]
                if not matching_indexes:
                    continue

                for candidate_index in matching_indexes:
                    size = normalize_size(candidates[candidate_index].get("size") or "")
                    dimensions = re.match(r"(\d{2,4})x(\d{2,4})", size or "")
                    aspect = int(dimensions.group(1)) / int(dimensions.group(2)) if dimensions else 1.0
                    crop_width = right - left
                    crop_height = crop_width / aspect if aspect > 0 else crop_width
                    candidate_bbox = candidates[candidate_index]["bbox"]
                    crop_bottom = min(image_bbox[3], candidate_bbox[1] - 8)
                    if crop_bottom - crop_height < image_bbox[1]:
                        crop_bottom = image_bbox[3]
                    crop_top = max(image_bbox[1], crop_bottom - crop_height)
                    actual_height = crop_bottom - crop_top
                    actual_width = min(crop_width, actual_height * aspect)
                    center_x = (left + right) / 2
                    crop_left = max(left, center_x - actual_width / 2)
                    crop_right = min(right, crop_left + actual_width)
                    if crop_right - crop_left >= 25 and actual_height >= 25:
                        cells[candidate_index] = (crop_left, crop_top, crop_right, crop_bottom)
    return cells


# ============================================================
# SPATIAL CATALOG PARSER
# ============================================================

logger = logging.getLogger("ceramic_ai.extraction")
if os.getenv("CERAMIC_AI_DEBUG", "").lower() in {"1", "true", "yes"}:
    logging.basicConfig(level=logging.DEBUG, format="%(levelname)s %(name)s %(message)s")


def normalize_size(value: str) -> Optional[str]:
    match = SIZE_REGEX.search(value.replace("\n", " "))
    if not match:
        return None
    size = re.sub(r"\s+", "", match.group(0)).replace("×", "x").replace("X", "x").replace("*", "x")
    return size.lower().replace("mm", "mm").replace("cm", "cm")


def is_product_code(value: str) -> bool:
    code = value.strip().upper().strip(":,.;")
    if not CODE_REGEX.fullmatch(code) or CERTIFICATION_REGEX.match(code):
        return False
    if re.fullmatch(r"(?:RANDOM|COLOR|COLOUR)[-/]?\d+", code):
        return False
    if normalize_size(code) or re.fullmatch(r"\d{1,4}", code):
        return False
    return any(char.isalpha() for char in code) and any(char.isdigit() for char in code)


def text_lines_from_page(page: pymupdf.Page) -> List[Dict[str, Any]]:
    lines = []
    for block_index, block in enumerate(page.get_text("dict").get("blocks", [])):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            spans = line.get("spans", [])
            text = normalize_text("".join(span.get("text", "") for span in spans))
            if not text:
                continue
            bbox = line.get("bbox", block.get("bbox", (0, 0, 0, 0)))
            lines.append({"text": text, "bbox": tuple(bbox), "block": block_index})
    return sorted(lines, key=lambda line: (round(line["bbox"][1], 1), line["bbox"][0]))


def ocr_page_lines(page: pymupdf.Page) -> List[Dict[str, Any]]:
    if not shutil.which("tesseract"):
        logger.warning("OCR skipped: Tesseract executable is unavailable")
        return []
    try:
        import pytesseract

        pixmap = page.get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False)
        image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
        data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
        grouped: Dict[tuple, List[int]] = {}
        for index, text in enumerate(data["text"]):
            if text.strip():
                key = (data["block_num"][index], data["par_num"][index], data["line_num"][index])
                grouped.setdefault(key, []).append(index)
        lines = []
        for indexes in grouped.values():
            text = normalize_text(" ".join(data["text"][index] for index in indexes))
            scale = 2
            x0 = min(data["left"][index] for index in indexes) / scale
            y0 = min(data["top"][index] for index in indexes) / scale
            x1 = max(data["left"][index] + data["width"][index] for index in indexes) / scale
            y1 = max(data["top"][index] + data["height"][index] for index in indexes) / scale
            lines.append({"text": text, "bbox": (x0, y0, x1, y1), "block": -1})
        lines.sort(key=lambda line: (round(line["bbox"][1], 1), line["bbox"][0]))
        columns = []
        for line in lines:
            matching_column = next((column for column in columns if abs(column["x"] - line["bbox"][0]) < 180 and 0 <= line["bbox"][1] - column["bottom"] <= 80), None)
            if matching_column:
                line["block"] = matching_column["id"]
                matching_column["bottom"] = line["bbox"][3]
            else:
                line["block"] = len(columns)
                columns.append({"id": line["block"], "x": line["bbox"][0], "bottom": line["bbox"][3]})
        return lines
    except Exception as error:
        logger.warning("OCR failed for page: %s", error)
        return []


def detect_page_context(lines: List[Dict[str, Any]]) -> tuple:
    text = "\n".join(line["text"] for line in lines)
    collection = None
    for line in lines:
        match = re.search(r"\b([A-Z][A-Z0-9 &'/-]{1,50}?)\s+COLLECTION\b", line["text"], re.IGNORECASE)
        if match:
            candidate = normalize_text(match.group(1)).strip(" -")
            if candidate and len(candidate) <= 45:
                collection = candidate.title()
                break

    category = None
    for pattern, label in (
        (r"\bSANITARYWARE\b", "Sanitaryware"),
        (r"\b(?:CERAMIC|VITRIFIED|PORCELAIN)\s+TILES?\b", "Ceramic & Vitrified Tiles"),
        (r"\b(?:FAUCET|MIXER|BIB TAP|PILLAR TAP|ANGLE VALVE|BATH SPOUT)S?\b", "Faucets & Fittings"),
    ):
        if re.search(pattern, text, re.IGNORECASE):
            category = label
            break
    return collection, category


def is_likely_product_name(value: str) -> bool:
    text = normalize_text(value).strip(" |:-")
    if not 3 <= len(text) <= 80 or not re.search(r"[A-Za-z]", text):
        return False
    if SIZE_REGEX.search(text) or CODE_REGEX.search(text) or re.search(r"(?:₹|Rs\.?|INR)\s*[\d,]+(?:\.\d{2})?", text, re.IGNORECASE):
        return False
    rejected = ("collection", "series", "catalog", "catalogue", "page", "list", "surface", "texture", "size", "finish", "iso", "standard", "specification", "thickness", "scan for", "colors", "colour")
    if any(term in text.lower() for term in rejected):
        return False
    return text.lower() not in FINISH_MAP


def extract_product_records(lines: List[Dict[str, Any]], page_text: str, filename: str, page_num: int) -> List[Dict[str, Any]]:
    records = []
    handled = set()

    # Explicit table rows are the strongest signal and keep each variant separate.
    for line in lines:
        if "|" not in line["text"]:
            continue
        cells = [normalize_text(cell) for cell in line["text"].split("|")]
        if len(cells) < 3 or not PRODUCT_ROW_REGEX.match(cells[0]):
            continue
        size = next((normalize_size(cell) for cell in cells if normalize_size(cell)), None)
        name = next((cell for cell in cells[1:] if is_likely_product_name(cell)), None)
        if not size or not name:
            continue
        surface = next((cell.title() for cell in cells[1:] if cell.lower() in {"brick", "soil", "polished", "matt", "matte", "glossy", "carving", "rocker", "protect", "satin", "sugar", "leather"}), None)
        records.append({"name": name, "size": size, "surface": surface, "finish": None, "bbox": line["bbox"], "code": None})
        handled.add((line["block"], line["text"]))

    # Catalog labels commonly place a role, product name, dimensions and surface
    # on separate PDF lines. Keep the association within the same text block.
    by_block: Dict[int, List[Dict[str, Any]]] = {}
    for line in lines:
        by_block.setdefault(line["block"], []).append(line)
    for block_lines in by_block.values():
        for index, line in enumerate(block_lines):
            row_match = PRODUCT_ROW_REGEX.match(line["text"])
            if not row_match:
                continue
            tail = row_match.group(1).strip(" |:-")
            segment = [line]
            for following in block_lines[index + 1:index + 7]:
                if PRODUCT_ROW_REGEX.match(following["text"]):
                    break
                segment.append(following)
            segment_text = " ".join(part["text"] for part in segment)
            name = tail if is_likely_product_name(tail) else None
            if not name:
                name = next((part["text"] for part in segment[1:] if is_likely_product_name(part["text"])), None)
            size = normalize_size(segment_text)
            if not name or not size:
                continue
            if any((part["block"], part["text"]) in handled for part in segment):
                continue
            surface = None
            finish = None
            for part in segment:
                match = re.search(r"\b(?:surface|texture)\s*[-:]?\s*([A-Za-z][A-Za-z -]{1,25})", part["text"], re.IGNORECASE)
                if match:
                    value = normalize_text(match.group(1)).strip(" -")
                    if value and value.lower() not in {"size", "mm", "cm"}:
                        if re.search(r"\btexture\b", part["text"], re.IGNORECASE):
                            finish = "SCS Matt" if value.lower() == "scs matt" else value.title()
                        else:
                            surface = "SCS Matt" if value.lower() == "scs matt" else value.title()
                        break
            bbox = (line["bbox"][0], line["bbox"][1], max(part["bbox"][2] for part in segment), max(part["bbox"][3] for part in segment))
            records.append({"name": name, "size": size, "surface": surface, "finish": finish, "bbox": bbox, "code": None})

    # Product-code records require nearby descriptive text or a product image;
    # standards, dimensions, prices and page numbers are rejected before matching.
    for line in lines:
        for match in CODE_REGEX.finditer(line["text"]):
            code = next((group for group in match.groups() if group), "").upper()
            if not is_product_code(code):
                logger.debug("%s page %s rejected code %s: invalid code pattern, dimension, or page number", filename, page_num, code)
                continue
            if re.search(r"\b(?:ISO|EN|ANSI|ASTM|BIS|IS|DIN)\b", line["text"], re.IGNORECASE):
                logger.debug("%s page %s rejected code %s: certification context", filename, page_num, code)
                continue
            center_x = (line["bbox"][0] + line["bbox"][2]) / 2
            center_y = (line["bbox"][1] + line["bbox"][3]) / 2
            nearby = [
                candidate
                for candidate in lines
                if candidate is not line
                and abs((candidate["bbox"][0] + candidate["bbox"][2]) / 2 - center_x) < 260
                and abs((candidate["bbox"][1] + candidate["bbox"][3]) / 2 - center_y) < 130
            ]
            local_text = " ".join([line["text"]] + [candidate["text"] for candidate in nearby])
            if re.search(r"@|\b(?:address|telephone|tel\.?|e-mail|email|mob\.?|sector|road|highway|pin code|toll free)\b", local_text, re.IGNORECASE):
                logger.debug("%s page %s rejected code %s: contact/address context", filename, page_num, code)
                continue
            name_candidate = next((candidate["text"] for candidate in sorted(nearby, key=lambda item: abs((item["bbox"][1] + item["bbox"][3]) / 2 - center_y) + abs((item["bbox"][0] + item["bbox"][2]) / 2 - center_x) * 0.25) if is_likely_product_name(candidate["text"])), None)
            if not name_candidate and not re.search(r"\b(?:tap|mixer|basin|shower|toilet|faucet|valve|sanitaryware)\b", local_text, re.IGNORECASE):
                logger.debug("%s page %s rejected code %s: no nearby product name or type", filename, page_num, code)
                continue
            records.append({"name": name_candidate, "size": None, "surface": None, "finish": None, "bbox": line["bbox"], "code": code})
    return records


def parse_catalog_document(doc: pymupdf.Document, filename: str) -> List[Dict[str, Any]]:
    safe_doc = clean_doc_name(filename)
    output_dir = get_images_output_dir(safe_doc)
    products = []

    for page_index, page in enumerate(doc):
        page_num = page_index + 1
        lines = text_lines_from_page(page)
        native_text = " ".join(line["text"] for line in lines)
        alpha_count = sum(char.isalpha() for char in native_text)
        if alpha_count < 40 and page.get_images():
            ocr_lines = ocr_page_lines(page)
            if len(" ".join(line["text"] for line in ocr_lines)) > len(native_text):
                lines = ocr_lines
                native_text = " ".join(line["text"] for line in lines)

        collection, category = detect_page_context(lines)
        candidates = extract_product_records(lines, native_text, filename, page_num)
        page_images = eligible_image_placements(page, candidates, lines)

        selected_images = []
        for candidate in candidates:
            matches = [
                (image_distance_to_candidate(image["bbox"], candidate["bbox"]), image_index)
                for image_index, image in enumerate(page_images)
            ]
            matches = [(distance, image_index) for distance, image_index in matches if distance is not None]
            selected_images.append(min(matches, key=lambda match: match[0])[1] if matches else None)
        image_usage = {}
        for image_index in selected_images:
            if image_index is not None:
                image_usage[image_index] = image_usage.get(image_index, 0) + 1
        image_cells = aligned_image_cells(candidates, selected_images, page_images, lines)

        accepted = 0
        for candidate_index, candidate in enumerate(candidates):
            name = candidate["name"]
            code = candidate["code"]
            if not name and not code:
                logger.debug("%s page %s rejected candidate %s: no product name or code", filename, page_num, candidate)
                continue
            bbox = candidate["bbox"]
            image_index = selected_images[candidate_index]
            nearest_image = page_images[image_index] if image_index is not None and image_usage[image_index] == 1 else None
            image_path = None
            prefix = f"p{page_num}-{candidate_index + 1}-{clean_doc_name(name or code)}"
            if nearest_image:
                if nearest_image.get("xref"):
                    image_path = save_image_from_xref(doc, nearest_image["xref"], output_dir, safe_doc, prefix)
                if not image_path:
                    image_path = crop_image_from_bbox(page, nearest_image["bbox"], output_dir, safe_doc, prefix)
                logger.debug("%s page %s candidate image=%s bbox=%s saved=%s", filename, page_num, nearest_image.get("xref"), nearest_image["bbox"], image_path)
            elif candidate_index in image_cells:
                image_path = crop_image_from_xref(doc, page_images[image_index], image_cells[candidate_index], output_dir, safe_doc, prefix)
                if not image_path:
                    image_path = crop_image_from_bbox(page, image_cells[candidate_index], output_dir, safe_doc, prefix, padding=0)
                logger.debug("%s page %s candidate image=%s bbox=%s crop=aligned-column cell=%s saved=%s", filename, page_num, page_images[image_index].get("xref"), page_images[image_index]["bbox"], image_cells[candidate_index], image_path)

            product = {
                "productCode": code,
                "productName": name,
                "category": category,
                "collection": collection,
                "size": candidate["size"],
                "surface": candidate["surface"],
                "finish": candidate["finish"],
                "color": None,
                "image": image_path,
                "sourceFile": filename,
                "sourcePage": page_num,
                "pages": [page_num],
            }
            products.append(product)
            accepted += 1
            logger.debug("%s page %s accepted product code=%s name=%s size=%s surface=%s", filename, page_num, code, name, candidate["size"], candidate["surface"])

        logger.debug("%s page %s text=%s blocks=%s candidates=%s accepted=%s rejected=%s", filename, page_num, len(native_text), len(page.get_text("blocks")), len(candidates), accepted, len(candidates) - accepted)

    # Collapse only exact repeated candidates from the same page and source.
    deduped = {}
    duplicate_records = 0
    for product in products:
        identity_fields = ("sourceFile", "sourcePage", "productCode", "productName", "size", "surface", "finish", "category", "collection")
        identity = tuple(str(product.get(field) or "").strip().lower() for field in identity_fields)
        if not any(identity[2:]):
            logger.debug("%s page %s duplicateKey=%s accepted=false reason=no product identity", filename, product.get("sourcePage"), identity)
            continue
        logger.debug("%s page %s candidate=%s duplicateKey=%s", filename, product.get("sourcePage"), product, identity)
        if identity in deduped:
            duplicate_records += 1
            logger.debug("%s page %s duplicateKey=%s accepted=false reason=exact duplicate candidate on same page", filename, product.get("sourcePage"), identity)
            continue
        deduped[identity] = product
        logger.debug("%s page %s duplicateKey=%s accepted=true reason=first occurrence on source page", filename, product.get("sourcePage"), identity)
    logger.info("%s: %s candidates, %s unique variants, %s duplicate records consolidated", filename, len(products), len(deduped), duplicate_records)
    return list(deduped.values())


# ============================================================
# EXTRACT ENDPOINT (SYNCHRONOUS FOR FASTAPI WORKER THREADPOOL)
# ============================================================

@app.post("/extract")
def extract_pdf(
    file: UploadFile = File(...)
):
    filename = file.filename or "document.pdf"

    if not filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are allowed"
        )

    try:
        pdf_bytes = file.file.read()
        if not pdf_bytes or len(pdf_bytes) < 50:
            raise HTTPException(
                status_code=400,
                detail="Uploaded PDF is empty or invalid"
            )
        if b"%PDF-" not in pdf_bytes[:1024]:
            raise HTTPException(
                status_code=400,
                detail="Uploaded file does not have a valid PDF signature"
            )

        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        pages = len(doc)
        if pages <= 0:
            raise HTTPException(
                status_code=400,
                detail="PDF contains no pages"
            )

        products = parse_catalog_document(doc, filename)
        doc.close()

        print(f"[AI SERVICE] Successfully extracted {len(products)} products from {filename} ({pages} pages)")

        return {
            "success": True,
            "message": "PDF processed successfully",
            "version": "5.0.0",
            "filename": filename,
            "pages": pages,
            "totalProducts": len(products),
            "products": products
        }

    except HTTPException:
        raise
    except Exception as error:
        print(f"[AI SERVICE] PDF extraction error for {filename}: {error}")
        raise HTTPException(
            status_code=500,
            detail=f"PDF extraction failed: {str(error)}"
        )