from fastapi import FastAPI, UploadFile, File, HTTPException
from pypdf import PdfReader
from PIL import Image
import pymupdf
import os
import io
import re
import hashlib
from typing import Any, Dict, List, Optional


# ============================================================
# APP
# ============================================================

app = FastAPI(
    title="Ceramic AI Service",
    version="4.0.0"
)


# ============================================================
# ROOT
# ============================================================

@app.get("/")
def root():
    return {
        "success": True,
        "message": "Ceramic AI Python service is running",
        "version": "4.0.0"
    }


# ============================================================
# HEALTH
# ============================================================

@app.get("/health")
def health():
    return {
        "success": True,
        "service": "ai-service",
        "status": "healthy",
        "version": "4.0.0"
    }


# ============================================================
# NORMALIZATION
# ============================================================

def normalize_text(text: Any) -> str:
    if text is None:
        return ""

    text = str(text)

    text = text.replace("\r\n", "\n")
    text = text.replace("\r", "\n")
    text = text.replace("\u00a0", " ")

    text = text.replace("ﬁ", "fi")
    text = text.replace("ﬂ", "fl")

    text = re.sub(r"[\u200b-\u200d\uFEFF]", "", text)

    text = re.sub(r"[ \t]+", " ", text)

    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def normalize_line(line: Any) -> str:
    line = normalize_text(line)
    line = re.sub(r"\s+", " ", line)
    return line.strip()


def clean_value(value: Any) -> Optional[str]:
    if value is None:
        return None

    value = normalize_line(value)

    if not value:
        return None

    return value


# ============================================================
# UNIQUE LIST
# ============================================================

def unique_list(values: Any) -> List[Any]:

    if values is None:
        return []

    if isinstance(values, (str, int, float)):
        values = [values]

    if not isinstance(values, (list, tuple, set)):
        return []

    result = []

    for value in values:

        if value is None:
            continue

        if isinstance(value, (int, float)):

            if value not in result:
                result.append(value)

            continue

        value = normalize_line(value)

        if not value:
            continue

        if not any(
            str(existing).lower() == value.lower()
            for existing in result
        ):
            result.append(value)

    return result


# ============================================================
# SIZE
# ============================================================

SIZE_PATTERNS = [

    r"\b\d{2,4}\s*[x×X]\s*\d{2,4}\s*mm\b",

    r"\b\d{2,4}\s*\*\s*\d{2,4}\s*mm\b",

    r"\b\d{2,4}\s+by\s+\d{2,4}\s*mm\b",
]


def normalize_size(value: str) -> Optional[str]:

    if not value:
        return None

    value = normalize_line(value)

    match = re.search(
        r"(\d{2,4})\s*[x×X*]\s*(\d{2,4})\s*mm",
        value,
        re.IGNORECASE
    )

    if match:
        return (
            f"{match.group(1)}x{match.group(2)}mm"
        ).lower()

    match = re.search(
        r"(\d{2,4})\s+by\s+(\d{2,4})\s*mm",
        value,
        re.IGNORECASE
    )

    if match:
        return (
            f"{match.group(1)}x{match.group(2)}mm"
        ).lower()

    return None


def find_sizes(text: str) -> List[str]:

    if not text:
        return []

    text = normalize_text(text)

    result = []

    for pattern in SIZE_PATTERNS:

        matches = re.findall(
            pattern,
            text,
            re.IGNORECASE
        )

        for match in matches:

            if isinstance(match, tuple):
                raw = "x".join(match) + "mm"
            else:
                raw = match

            value = normalize_size(raw)

            if value and value not in result:
                result.append(value)

    # Handle broken PDF text:
    # 5 9 8 x 1 1 9 8 m m

    compact = re.sub(
        r"(?<=\d)\s+(?=\d)",
        "",
        text
    )

    matches = re.findall(
        r"\b(\d{2,4})\s*[x×X*]\s*(\d{2,4})\s*mm\b",
        compact,
        re.IGNORECASE
    )

    for match in matches:

        value = normalize_size(
            f"{match[0]}x{match[1]}mm"
        )

        if value and value not in result:
            result.append(value)

    return result


# ============================================================
# FINISH
# ============================================================

FINISH_PATTERNS = [

    (r"\bprotect\b", "Protect"),
    (r"\bpolished\b", "Polished"),
    (r"\bpolish\b", "Polished"),
    (r"\bmatt\b", "Matt"),
    (r"\bmatte\b", "Matt"),
    (r"\bhoned\b", "Honed"),
    (r"\bsatin\b", "Satin"),
    (r"\bglossy\b", "Glossy"),
    (r"\bgloss\b", "Gloss"),
    (r"\blappato\b", "Lappato"),
    (r"\bcarving\b", "Carving"),
    (r"\bstructured\b", "Structured"),
    (r"\btextured\b", "Textured"),
]


def find_surface(text: str) -> List[str]:

    if not text:
        return []

    result = []

    for pattern, value in FINISH_PATTERNS:

        if re.search(
            pattern,
            text,
            re.IGNORECASE
        ):

            if value not in result:
                result.append(value)

    return result


# ============================================================
# TEXTURE
# ============================================================

TEXTURE_WORDS = [

    "Grid",
    "Dune",
    "Brick",
    "Soil",
    "Stone",
    "Wood",
    "Marble",
    "Concrete",
    "Terrazzo",
    "Slate",
    "Rock",
    "Flute",
    "Linear",
    "Wave",
    "Geometric",
    "Floral",
    "Petals",
    "Loop",
    "Geo",
    "Heritage",
]


def find_texture(text: str) -> List[str]:

    if not text:
        return []

    result = []

    for value in TEXTURE_WORDS:

        if re.search(
            rf"\b{re.escape(value)}\b",
            text,
            re.IGNORECASE
        ):

            result.append(value)

    return result


# ============================================================
# APPLICATION
# ============================================================

APPLICATION_PATTERNS = [

    (r"\bfloor\b", "Floor"),
    (r"\bwall\b", "Wall"),
    (r"\bflooring\b", "Floor"),
    (r"\bwalling\b", "Wall"),
    (r"\bindoor\b", "Indoor"),
    (r"\boutdoor\b", "Outdoor"),
]


def find_application(text: str) -> List[str]:

    if not text:
        return []

    result = []

    for pattern, value in APPLICATION_PATTERNS:

        if re.search(
            pattern,
            text,
            re.IGNORECASE
        ):

            if value not in result:
                result.append(value)

    return result


# ============================================================
# CATEGORY
# ============================================================

CATEGORY_PATTERNS = [

    (
        r"\bFULL\s*BODY\s+VITRIFIED\s+TILES?\b",
        "FULLBODY VITRIFIED TILES"
    ),

    (
        r"\bFULL\s*BODY\s+VITRIFIED\b",
        "FULLBODY VITRIFIED TILES"
    ),

    (
        r"\bFULL\s*BODY\s+PORCELAIN\s+TILES?\b",
        "FULL BODY PORCELAIN TILES"
    ),

    (
        r"\bFULL\s*BODY\s+PORCELAIN\b",
        "FULL BODY PORCELAIN TILES"
    ),

    (
        r"\bGLAZED\s+VITRIFIED\s+TILES?\b",
        "GLAZED VITRIFIED TILES"
    ),

    (
        r"\bGLAZED\s+VITRIFIED\b",
        "GLAZED VITRIFIED TILES"
    ),

    (
        r"\bGLAZED\s+PORCELAIN\s+TILES?\b",
        "GLAZED PORCELAIN TILES"
    ),

    (
        r"\bGLAZED\s+PORCELAIN\b",
        "GLAZED PORCELAIN TILES"
    ),

    (
        r"\bPORCELAIN\s+TILES?\b",
        "PORCELAIN TILES"
    ),

    (
        r"\bCERAMIC\s+TILES?\b",
        "CERAMIC TILES"
    ),

    (
        r"\bCERAMIC\b",
        "CERAMIC TILES"
    ),
]


def find_category(text: str) -> Optional[str]:

    if not text:
        return None

    normalized = normalize_text(text)

    for pattern, category in CATEGORY_PATTERNS:

        if re.search(
            pattern,
            normalized,
            re.IGNORECASE
        ):
            return category

    return None


# ============================================================
# COLLECTION
# ============================================================

def find_collection(text: str) -> Optional[str]:

    if not text:
        return None

    normalized = normalize_text(text)

    patterns = [

        r"\b([A-Za-z][A-Za-z0-9&'/-]*(?:\s+[A-Za-z][A-Za-z0-9&'/-]*){0,5})\s+COLLECTION\b",

        r"\bCOLLECTION\s*[:\-]\s*([A-Za-z0-9&' /-]+)",

    ]

    for pattern in patterns:

        matches = re.findall(
            pattern,
            normalized,
            re.IGNORECASE
        )

        for match in matches:

            value = normalize_line(match)

            if not value:
                continue

            if value.lower() == "collection":
                continue

            if len(value) > 80:
                continue

            return value.upper()

    return None


# ============================================================
# METADATA LABEL EXTRACTION
# ============================================================

def extract_labeled_value(
    text: str,
    labels: List[str]
) -> Optional[str]:

    if not text:
        return None

    lines = [
        normalize_line(x)
        for x in text.splitlines()
        if normalize_line(x)
    ]

    label_pattern = "|".join(
        re.escape(label)
        for label in labels
    )

    # Same-line:
    # Color: Beige
    # Colour - Grey
    # Design: Marble

    same_line = re.compile(
        rf"^\s*(?:{label_pattern})\s*"
        rf"[:\-–—]\s*(.+?)\s*$",
        re.IGNORECASE
    )

    for index, line in enumerate(lines):

        match = same_line.match(line)

        if match:

            value = clean_metadata_value(
                match.group(1)
            )

            if value:
                return value

        # Label and value separated:
        #
        # Colour
        # Beige

        if re.fullmatch(
            rf"(?:{label_pattern})",
            line,
            re.IGNORECASE
        ):

            if index + 1 < len(lines):

                value = clean_metadata_value(
                    lines[index + 1]
                )

                if value:
                    return value

    return None


def clean_metadata_value(value: str) -> Optional[str]:

    if not value:
        return None

    value = normalize_line(value)

    value = re.sub(
        r"^(?:[:\-–—|]+)\s*",
        "",
        value
    )

    # Stop accidental next metadata fields

    value = re.split(
        r"\b(?:size|surface|finish|texture|"
        r"application|collection|category|"
        r"colour|color|design)\s*[:\-–—]",
        value,
        maxsplit=1,
        flags=re.IGNORECASE
    )[0]

    value = normalize_line(value)

    if not value:
        return None

    if len(value) > 100:
        return None

    return value


def find_color(text: str) -> Optional[str]:

    return extract_labeled_value(
        text,
        [
            "Color",
            "Colour",
            "Colors",
            "Colours",
            "Shade",
            "Colour Name",
            "Color Name"
        ]
    )


def find_design(text: str) -> List[str]:

    value = extract_labeled_value(
        text,
        [
            "Design",
            "Design Name",
            "Pattern",
            "Pattern Name"
        ]
    )

    if not value:
        return []

    return [value]


# ============================================================
# PRODUCT NAME
# ============================================================

REJECTED_PRODUCT_NAMES = {

    "application",
    "collection",
    "options",
    "suggestions",
    "tiles",
    "tile",
    "floor",
    "wall",
    "surface",
    "texture",
    "protect",
    "polished",
    "matt",
    "matte",
    "base",
    "border",
    "corner",
    "size",
    "finish",
    "design",
    "colour",
    "color",
    "product",
    "products",
    "catalogue",
    "catalog",
    "contents",
    "index",
    "technical",
    "specification",
    "specifications",
    "pattern",
    "shade",
}


def clean_product_name(
    name: str
) -> Optional[str]:

    if not name:
        return None

    name = normalize_line(name)

    name = re.sub(
        r"^\s*[-–—]?\s*\d+\s*[-–—.)]?\s*",
        "",
        name
    )

    name = re.sub(
        r"\s*[-–—|:]+\s*$",
        "",
        name
    )

    if not name:
        return None

    if name.lower() in REJECTED_PRODUCT_NAMES:
        return None

    if not re.search(
        r"[A-Za-z]",
        name
    ):
        return None

    if len(name) > 80:
        return None

    return name


# ============================================================
# EXPLICIT FLOOR / WALL PRODUCT
# ============================================================

def extract_name_from_detail_line(
    line: str
):

    line = normalize_line(line)

    if not line:
        return None

    line = re.sub(
        r"^\d+\s+\d+\s+",
        "",
        line
    ).strip()

    pattern = re.compile(
        r"^(Floor|Wall)"
        r"(?:\s*[-–—:]?\s*\d+)?"
        r"\s+"
        r"(.+?)$",
        re.IGNORECASE
    )

    match = pattern.match(line)

    if not match:
        return None

    application = match.group(1).title()

    name = clean_product_name(
        match.group(2)
    )

    if not name:
        return None

    # Remove accidental metadata

    name = re.split(
        r"\b(?:Size|Surface|Texture|Collection|"
        r"Application|Finish|Design|Colour|Color)\b",
        name,
        maxsplit=1,
        flags=re.IGNORECASE
    )[0]

    name = clean_product_name(name)

    if not name:
        return None

    return {
        "name": name,
        "application": application
    }


# ============================================================
# GENERIC PRODUCT NAME HEURISTIC
# ============================================================

def looks_like_product_name(
    line: str
) -> bool:

    line = normalize_line(line)

    if not line:
        return False

    lower = line.lower()

    if lower in REJECTED_PRODUCT_NAMES:
        return False

    # Never accept obvious metadata

    metadata_words = [

        "size",
        "surface",
        "finish",
        "texture",
        "application",
        "collection",
        "technical",
        "specification",
        "thickness",
        "shade",
        "available",
        "packing",
        "pcs",
        "box",
        "sqm",
        "mm",
        "colour",
        "color",
        "design",
        "pattern",
        "catalogue",
        "catalog",
    ]

    for word in metadata_words:

        if re.search(
            rf"\b{re.escape(word)}\b",
            lower
        ):
            return False

    if not re.search(
        r"[A-Za-z]",
        line
    ):
        return False

    if re.search(
        r"\d{2,4}\s*[x×X*]\s*\d{2,4}",
        line
    ):
        return False

    if len(line.split()) > 7:
        return False

    if len(line) > 70:
        return False

    # Avoid obvious headings

    heading_words = [
        "welcome",
        "contents",
        "introduction",
        "technical data",
        "technical specification",
        "index",
        "contact us",
        "about us",
    ]

    if lower in heading_words:
        return False

    return True


# ============================================================
# GENERIC BLOCK PARSER
# ============================================================

def parse_detail_blocks(
    page_text: str
):

    raw_lines = page_text.splitlines()

    lines = []

    for raw in raw_lines:

        line = normalize_line(raw)

        if line:
            lines.append(line)

    candidates = []

    # --------------------------------------------------------
    # PASS 1
    # Explicit Floor / Wall product lines
    # --------------------------------------------------------

    explicit_indexes = []

    for index, line in enumerate(lines):

        detail = extract_name_from_detail_line(line)

        if detail:
            explicit_indexes.append(
                (index, detail)
            )

    for position, (index, detail) in enumerate(
        explicit_indexes
    ):

        if position + 1 < len(explicit_indexes):

            end_index = explicit_indexes[
                position + 1
            ][0]

        else:

            end_index = len(lines)

        block_lines = lines[
            index:end_index
        ]

        block_text = "\n".join(
            block_lines
        )

        sizes = find_sizes(block_text)
        finishes = find_surface(block_text)
        textures = find_texture(block_text)

        color = find_color(block_text)
        design = find_design(block_text)

        candidates.append({

            "productName":
                detail["name"],

            "application":
                [detail["application"]],

            "size":
                unique_list(sizes),

            "finish":
                unique_list(finishes),

            "texture":
                unique_list(textures),

            "color":
                color,

            "design":
                unique_list(design),

            "lineIndex":
                index,

            "blockText":
                block_text
        })

    # --------------------------------------------------------
    # PASS 2
    # Generic layout
    #
    # Product name may be on its own line.
    #
    # Example:
    #
    # BLACK BEACH
    # 598x598mm
    # Protect
    # Dune
    # Colour: Black
    # Design: Stone
    # --------------------------------------------------------

    used_names = {
        c["productName"].lower()
        for c in candidates
        if c.get("productName")
    }

    for index, line in enumerate(lines):

        if not looks_like_product_name(line):
            continue

        name = clean_product_name(line)

        if not name:
            continue

        if name.lower() in used_names:
            continue

        # ----------------------------------------------------
        # Look around product name.
        # ----------------------------------------------------

        start = max(
            0,
            index - 2
        )

        end = min(
            len(lines),
            index + 15
        )

        nearby_lines = lines[
            start:end
        ]

        nearby_text = "\n".join(
            nearby_lines
        )

        sizes = find_sizes(
            nearby_text
        )

        finishes = find_surface(
            nearby_text
        )

        textures = find_texture(
            nearby_text
        )

        application = find_application(
            nearby_text
        )

        color = find_color(
            nearby_text
        )

        design = find_design(
            nearby_text
        )

        # ----------------------------------------------------
        # Strong evidence
        #
        # Generic name is accepted only when nearby metadata
        # proves that this is likely a tile product.
        # ----------------------------------------------------

        evidence_count = 0

        if sizes:
            evidence_count += 1

        if finishes:
            evidence_count += 1

        if textures:
            evidence_count += 1

        if color:
            evidence_count += 1

        if design:
            evidence_count += 1

        if not application:
            application = []

        # At least one strong tile-related signal
        if evidence_count == 0:
            continue

        candidates.append({

            "productName":
                name,

            "application":
                unique_list(application),

            "size":
                unique_list(sizes),

            "finish":
                unique_list(finishes),

            "texture":
                unique_list(textures),

            "color":
                color,

            "design":
                unique_list(design),

            "lineIndex":
                index,

            "blockText":
                nearby_text
        })

        used_names.add(
            name.lower()
        )

    return candidates


# ============================================================
# PAGE CONTEXT
# ============================================================

def build_page_category_context(
    page_text: str
):

    return {

        "category":
            find_category(page_text),

        "collection":
            find_collection(page_text)
    }


# ============================================================
# PRODUCT KEY
# ============================================================

def product_key(product):

    name = normalize_line(
        product.get(
            "productName",
            ""
        )
    ).lower()

    return name


# ============================================================
# MERGE PRODUCTS
# ============================================================

def merge_products(products):

    merged = {}

    for product in products:

        key = product_key(product)

        if not key:
            continue

        if key not in merged:

            merged[key] = {

                "productName":
                    product.get(
                        "productName"
                    ),

                "category":
                    product.get(
                        "category"
                    ),

                "collection":
                    product.get(
                        "collection"
                    ),

                "size":
                    unique_list(
                        product.get(
                            "size"
                        )
                    ),

                "finish":
                    unique_list(
                        product.get(
                            "finish"
                        )
                    ),

                "texture":
                    unique_list(
                        product.get(
                            "texture"
                        )
                    ),

                "application":
                    unique_list(
                        product.get(
                            "application"
                        )
                    ),

                "color":
                    product.get(
                        "color"
                    ),

                "design":
                    unique_list(
                        product.get(
                            "design"
                        )
                    ),

                "image":
                    product.get(
                        "image"
                    ),

                "images":
                    unique_list(
                        product.get(
                            "images"
                        )
                    ),

                "pages":
                    unique_list(
                        product.get(
                            "pages"
                        )
                    )
            }

            continue

        existing = merged[key]

        existing["size"] = unique_list(
            existing.get("size", [])
            +
            unique_list(
                product.get("size")
            )
        )

        existing["finish"] = unique_list(
            existing.get("finish", [])
            +
            unique_list(
                product.get("finish")
            )
        )

        existing["texture"] = unique_list(
            existing.get("texture", [])
            +
            unique_list(
                product.get("texture")
            )
        )

        existing["application"] = unique_list(
            existing.get("application", [])
            +
            unique_list(
                product.get("application")
            )
        )

        existing["design"] = unique_list(
            existing.get("design", [])
            +
            unique_list(
                product.get("design")
            )
        )

        # ----------------------------------------------------
        # Color
        # Never overwrite a real value with None.
        # ----------------------------------------------------

        if not existing.get("color"):

            new_color = product.get(
                "color"
            )

            if new_color:
                existing["color"] = new_color

        # ----------------------------------------------------
        # Category / Collection
        # ----------------------------------------------------

        if not existing.get("category"):

            existing["category"] = product.get(
                "category"
            )

        if not existing.get("collection"):

            existing["collection"] = product.get(
                "collection"
            )

        # ----------------------------------------------------
        # Image
        # ----------------------------------------------------

        if not existing.get("image"):

            existing["image"] = product.get(
                "image"
            )

        existing["images"] = unique_list(
            existing.get("images", [])
            +
            unique_list(
                product.get("images")
            )
        )

        existing["pages"] = sorted(
            set(
                int(page)
                for page in (
                    unique_list(
                        existing.get("pages")
                    )
                    +
                    unique_list(
                        product.get("pages")
                    )
                )
                if str(page).isdigit()
            )
        )

    return list(
        merged.values()
    )


# ============================================================
# PRODUCT EXTRACTION
# ============================================================

def extract_products_from_pdf(
    reader
):

    detected = []

    page_count = len(
        reader.pages
    )

    page_texts = {}

    # --------------------------------------------------------
    # Extract all page text
    # --------------------------------------------------------

    for page_number, page in enumerate(
        reader.pages,
        start=1
    ):

        try:

            text = (
                page.extract_text()
                or ""
            )

            page_texts[
                page_number
            ] = normalize_text(text)

        except Exception as error:

            print(
                f"Text extraction failed "
                f"page={page_number}: {error}"
            )

            page_texts[
                page_number
            ] = ""

    active_category = None
    active_collection = None

    # --------------------------------------------------------
    # Process pages
    # --------------------------------------------------------

    for page_number in range(
        1,
        page_count + 1
    ):

        page_text = page_texts.get(
            page_number,
            ""
        )

        if not page_text:
            continue

        context = build_page_category_context(
            page_text
        )

        page_category = context.get(
            "category"
        )

        page_collection = context.get(
            "collection"
        )

        if page_category:
            active_category = page_category

        if page_collection:
            active_collection = page_collection

        candidates = parse_detail_blocks(
            page_text
        )

        if not candidates:
            continue

        for candidate in candidates:

            name = candidate.get(
                "productName"
            )

            if not name:
                continue

            category = (
                page_category
                or active_category
            )

            collection = (
                page_collection
                or active_collection
            )

            detected.append({

                "productName":
                    name,

                "category":
                    category,

                "collection":
                    collection,

                "size":
                    unique_list(
                        candidate.get(
                            "size"
                        )
                    ),

                "finish":
                    unique_list(
                        candidate.get(
                            "finish"
                        )
                    ),

                "texture":
                    unique_list(
                        candidate.get(
                            "texture"
                        )
                    ),

                "application":
                    unique_list(
                        candidate.get(
                            "application"
                        )
                    ),

                "color":
                    candidate.get(
                        "color"
                    ),

                "design":
                    unique_list(
                        candidate.get(
                            "design"
                        )
                    ),

                "image":
                    None,

                "images":
                    [],

                "pages":
                    [page_number]
            })

    return merge_products(
        detected
    )


# ============================================================
# IMAGE VALIDATION
# ============================================================

def valid_image_bytes(data):

    if not data:
        return False

    try:

        image = Image.open(
            io.BytesIO(data)
        )

        image.load()

        width, height = image.size

        if width < 100 or height < 100:
            return False

        if width < 30 or height < 30:
            return False

        return True

    except Exception:

        return False


# ============================================================
# IMAGE HASH
# ============================================================

def image_hash(data):

    try:

        return hashlib.sha1(
            data
        ).hexdigest()

    except Exception:

        return None


# ============================================================
# PRODUCT NAME SEARCH
# ============================================================

def find_product_rects(
    page,
    product_name
):

    rects = []

    try:

        rects = page.search_for(
            product_name
        )

        if rects:
            return rects

        target = normalize_line(
            product_name
        ).lower()

        blocks = page.get_text(
            "blocks"
        )

        for block in blocks:

            text = normalize_line(
                block[4]
            )

            if target in text.lower():

                rects.append(
                    pymupdf.Rect(
                        block[0],
                        block[1],
                        block[2],
                        block[3]
                    )
                )

    except Exception as error:

        print(
            "Product position error:",
            error
        )

    return rects


# ============================================================
# PRODUCT IMAGE CROP
# ============================================================

def crop_product_image(
    doc,
    product,
    filename
):

    pages = product.get(
        "pages"
    ) or []

    if not pages:
        return product

    try:

        base_name = os.path.splitext(
            filename or "document"
        )[0]

        safe_document = re.sub(
            r"[^a-zA-Z0-9_-]",
            "_",
            base_name
        )

        output_dir = os.path.join(
            "extracted_images",
            safe_document,
            "product_crops"
        )

        os.makedirs(
            output_dir,
            exist_ok=True
        )

        product_name = product.get(
            "productName"
        )

        if not product_name:
            return product

        for page_number in pages:

            if not page_number:
                continue

            if page_number < 1:
                continue

            if page_number > len(doc):
                continue

            page = doc[
                page_number - 1
            ]

            rects = find_product_rects(
                page,
                product_name
            )

            if not rects:
                continue

            rect = None

            for candidate_rect in rects:

                if (
                    candidate_rect.width >= 10
                    and
                    candidate_rect.height >= 5
                ):

                    rect = candidate_rect
                    break

            if rect is None:
                rect = rects[0]

            page_width = page.rect.width
            page_height = page.rect.height

            crop_left = max(
                0,
                rect.x0 - 180
            )

            crop_right = min(
                page_width,
                rect.x1 + 180
            )

            crop_top = max(
                0,
                rect.y0 - 120
            )

            crop_bottom = min(
                page_height,
                rect.y1 + 180
            )

            crop_rect = pymupdf.Rect(
                crop_left,
                crop_top,
                crop_right,
                crop_bottom
            )

            if crop_rect.width < 80:
                continue

            if crop_rect.height < 80:
                continue

            pix = page.get_pixmap(
                matrix=pymupdf.Matrix(
                    2.5,
                    2.5
                ),
                clip=crop_rect,
                alpha=False
            )

            safe_product = re.sub(
                r"[^a-zA-Z0-9]+",
                "-",
                product_name.lower()
            ).strip("-")

            image_name = (
                f"page-{page_number}-"
                f"{safe_product}.png"
            )

            image_path = os.path.join(
                output_dir,
                image_name
            )

            pix.save(
                image_path
            )

            relative_path = os.path.join(
                "extracted_images",
                safe_document,
                "product_crops",
                image_name
            )

            product["image"] = relative_path

            product["images"] = [
                {
                    "page":
                        page_number,

                    "image":
                        image_name,

                    "path":
                        relative_path,

                    "type":
                        "product_detail_crop"
                }
            ]

            return product

    except Exception as error:

        print(
            f"Product image mapping failed "
            f"for {product.get('productName')}: "
            f"{error}"
        )

    return product


# ============================================================
# MAP PRODUCT IMAGES
# ============================================================

def map_product_images(
    products,
    pdf_bytes,
    filename
):

    if not products:
        return products

    doc = None

    try:

        doc = pymupdf.open(
            stream=pdf_bytes,
            filetype="pdf"
        )

        for product in products:

            crop_product_image(
                doc,
                product,
                filename
            )

    except Exception as error:

        print(
            "Product image mapping error:",
            error
        )

    finally:

        if doc is not None:

            try:
                doc.close()
            except Exception:
                pass

    return products


# ============================================================
# FINAL CLEAN PRODUCT
# ============================================================

def clean_product(product):

    return {

        "productName":
            clean_value(
                product.get(
                    "productName"
                )
            ),

        "category":
            clean_value(
                product.get(
                    "category"
                )
            ),

        "collection":
            clean_value(
                product.get(
                    "collection"
                )
            ),

        "size":
            unique_list(
                product.get(
                    "size"
                )
            ) or None,

        "finish":
            unique_list(
                product.get(
                    "finish"
                )
            ) or None,

        "texture":
            unique_list(
                product.get(
                    "texture"
                )
            ) or None,

        "application":
            unique_list(
                product.get(
                    "application"
                )
            ) or None,

        "color":
            clean_value(
                product.get(
                    "color"
                )
            ),

        "design":
            unique_list(
                product.get(
                    "design"
                )
            ) or None,

        "image":
            product.get(
                "image"
            ),

        "images":
            product.get(
                "images"
            ) or [],

        "pages":
            unique_list(
                product.get(
                    "pages"
                )
            ) or []
    }


# ============================================================
# PDF VALIDATION
# ============================================================

def validate_pdf_bytes(
    pdf_bytes
):

    if not pdf_bytes:

        raise HTTPException(
            status_code=400,
            detail="Empty PDF file"
        )

    if not pdf_bytes.startswith(
        b"%PDF"
    ):

        raise HTTPException(
            status_code=400,
            detail="Invalid PDF file"
        )


# ============================================================
# PDF EXTRACTION API
# ============================================================

@app.post("/extract")
async def extract_pdf(
    file: UploadFile = File(...)
):

    filename = (
        file.filename
        or
        "document.pdf"
    )

    if not filename.lower().endswith(
        ".pdf"
    ):

        raise HTTPException(
            status_code=400,
            detail="Only PDF files are allowed"
        )

    try:

        # ----------------------------------------------------
        # Read PDF
        # ----------------------------------------------------

        pdf_bytes = await file.read()

        validate_pdf_bytes(
            pdf_bytes
        )

        # ----------------------------------------------------
        # Reader
        # ----------------------------------------------------

        reader = PdfReader(
            io.BytesIO(
                pdf_bytes
            )
        )

        pages = len(
            reader.pages
        )

        if pages <= 0:

            raise HTTPException(
                status_code=400,
                detail="PDF contains no pages"
            )

        # ----------------------------------------------------
        # Full text
        # ----------------------------------------------------

        all_text = []

        for page_number, page in enumerate(
            reader.pages,
            start=1
        ):

            try:

                text = (
                    page.extract_text()
                    or ""
                )

                all_text.append(
                    text
                )

            except Exception as page_error:

                print(
                    f"Text extraction failed "
                    f"page={page_number}: "
                    f"{page_error}"
                )

        full_text = normalize_text(
            "\n".join(
                all_text
            )
        )

        # ----------------------------------------------------
        # Products
        # ----------------------------------------------------

        products = extract_products_from_pdf(
            reader
        )

        # ----------------------------------------------------
        # Images
        # ----------------------------------------------------

        products = map_product_images(
            products,
            pdf_bytes,
            filename
        )

        # ----------------------------------------------------
        # Final
        # ----------------------------------------------------

        clean_products = [
            clean_product(product)
            for product in products
        ]

        return {

            "success":
                True,

            "message":
                "PDF processed successfully",

            "version":
                "4.0.0",

            "filename":
                filename,

            "pages":
                pages,

            "textLength":
                len(full_text),

            "totalProducts":
                len(clean_products),

            "products":
                clean_products
        }

    except HTTPException:

        raise

    except Exception as error:

        print(
            "PDF extraction error:",
            error
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "PDF extraction failed: "
                + str(error)
            )
        )