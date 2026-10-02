from fastapi import FastAPI, UploadFile, File, HTTPException
from pypdf import PdfReader
from PIL import Image
import pymupdf
import os
import io
import re
import hashlib


app = FastAPI(
    title="Ceramic AI Service",
    version="2.0.0"
)


# ============================================================
# ROOT
# ============================================================

@app.get("/")
def root():
    return {
        "success": True,
        "message": "Ceramic AI Python service is running"
    }


# ============================================================
# HEALTH
# ============================================================

@app.get("/health")
def health():
    return {
        "success": True,
        "service": "ai-service",
        "status": "healthy"
    }


# ============================================================
# NORMALIZATION
# ============================================================

def normalize_text(text):
    if not text:
        return ""

    text = str(text)
    text = text.replace("\r", "\n")
    text = text.replace("\u00a0", " ")

    # Fix common PDF ligature
    text = text.replace("", "fi")
    text = text.replace("", "fl")

    text = re.sub(r"[ \t]+", " ", text)

    return text.strip()


def normalize_line(line):
    line = normalize_text(line)
    line = re.sub(r"\s+", " ", line)
    return line.strip()


# ============================================================
# SIZE DETECTION
# ============================================================

def find_sizes(text):
    if not text:
        return []

    result = []

    # Normal:
    # 598x1198mm
    # 598 x 1198 mm
    # 598×1198mm

    normal_pattern = re.compile(
        r"\b\d{2,4}\s*[x×]\s*\d{2,4}\s*mm\b",
        re.IGNORECASE
    )

    for match in normal_pattern.findall(text):
        value = re.sub(r"\s+", "", match)
        value = value.replace("×", "x").lower()

        if value not in result:
            result.append(value)

    # PDF text sometimes becomes:
    # 5 9 8 x 1 1 9 8 m m

    spaced_patterns = {
        "598x1198mm":
            r"5\s*9\s*8\s*[x×]\s*1\s*1\s*9\s*8\s*m\s*m",

        "598x598mm":
            r"5\s*9\s*8\s*[x×]\s*5\s*9\s*8\s*m\s*m",

        "198x198mm":
            r"1\s*9\s*8\s*[x×]\s*1\s*9\s*8\s*m\s*m"
    }

    for size, pattern in spaced_patterns.items():
        if re.search(pattern, text, re.IGNORECASE):
            if size not in result:
                result.append(size)

    return result


# ============================================================
# SURFACE / FINISH
# ============================================================

SURFACE_WORDS = [
    "Protect",
    "Polished",
    "Matt"
]


def find_surface(text):
    if not text:
        return []

    result = []

    for value in SURFACE_WORDS:
        if re.search(
            rf"\b{re.escape(value)}\b",
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
    "Soil"
]


def find_texture(text):
    if not text:
        return []

    result = []

    for value in TEXTURE_WORDS:
        if re.search(
            rf"\b{re.escape(value)}\b",
            text,
            re.IGNORECASE
        ):
            if value not in result:
                result.append(value)

    return result


# ============================================================
# APPLICATION
# ============================================================

APPLICATION_WORDS = [
    "Floor",
    "Wall"
]


def find_application(text):
    if not text:
        return []

    result = []

    if re.search(r"\bFloor\b", text, re.IGNORECASE):
        result.append("Floor")

    if re.search(r"\bWall\b", text, re.IGNORECASE):
        result.append("Wall")

    return result


# ============================================================
# CATEGORY
# ============================================================

def find_category(text):
    if not text:
        return None

    if re.search(
        r"FULL\s*BODY\s+VITRI",
        text,
        re.IGNORECASE
    ):
        return "FULLBODY VITRIFIED TILES"

    if re.search(
        r"GLAZED\s+VITRI",
        text,
        re.IGNORECASE
    ):
        return "GLAZED VITRIFIED TILES"

    return None


# ============================================================
# COLLECTION
# ============================================================

def find_collection(text):
    if not text:
        return None

    matches = re.findall(
        r"\b([A-Z][A-Z\s&-]{2,40})\s+Collection\b",
        text,
        re.IGNORECASE
    )

    if matches:
        value = matches[0].strip()
        value = re.sub(r"\s+", " ", value)

        if value.lower() not in [
            "the",
            "this",
            "our"
        ]:
            return value.upper()

    if re.search(
        r"\bCOURTYARD\b",
        text,
        re.IGNORECASE
    ):
        return "COURTYARD"

    return None


# ============================================================
# PRODUCT NAME FROM DETAIL LINE
# ============================================================

def extract_name_from_detail_line(line):
    """
    Only accept names from lines that look like:

        Floor Black Beach
        Wall River Grey
        Floor - 2 Garden Loop
        Wall - 1 Silver Chalk

    We deliberately DO NOT consider random standalone
    text as a product.
    """

    line = normalize_line(line)

    if not line:
        return None

    # Remove page/catalogue noise attached to beginning
    line = re.sub(
        r"^\d+\s+\d+",
        "",
        line
    ).strip()

    # --------------------------------------------------------
    # Application + optional numbering + product name
    # --------------------------------------------------------

    pattern = re.compile(
        r"^(Floor|Wall)"
        r"(?:\s*-\s*\d+)?"
        r"\s+"
        r"([A-Za-z][A-Za-z0-9&'/-]*(?:\s+[A-Za-z][A-Za-z0-9&'/-]*){0,5})"
        r"$",
        re.IGNORECASE
    )

    match = pattern.match(line)

    if not match:
        return None

    application = match.group(1).title()
    name = normalize_line(match.group(2))

    # Remove accidental trailing metadata
    name = re.sub(
        r"\b(Size|Surface|Texture|Collection|Application)\b.*$",
        "",
        name,
        flags=re.IGNORECASE
    ).strip()

    if not name:
        return None

    # Reject obvious non-product text
    rejected = {
        "application",
        "collection",
        "options",
        "suggestions",
        "tiles",
        "floor",
        "wall",
        "surface",
        "texture",
        "protect",
        "polished",
        "matt",
        "base",
        "border",
        "corner"
    }

    if name.lower() in rejected:
        return None

    return {
        "name": name,
        "application": application
    }


# ============================================================
# DETAIL BLOCK PARSER
# ============================================================

def parse_detail_blocks(page_text):
    """
    Convert a page into real product-detail candidates.

    A candidate is accepted ONLY when:
        1. Floor/Wall application exists
        2. Product name exists
        3. Size exists
        4. Surface OR Texture exists

    This is the main false-positive protection.
    """

    raw_lines = page_text.splitlines()

    lines = []

    for raw in raw_lines:
        line = normalize_line(raw)

        if line:
            lines.append(line)

    candidates = []

    for index, line in enumerate(lines):

        detail = extract_name_from_detail_line(line)

        if not detail:
            continue

        name = detail["name"]
        application = detail["application"]

        # ----------------------------------------------------
        # Look around the detail line.
        # Product metadata may be split over next few lines.
        # ----------------------------------------------------

        context_parts = []

        start = max(0, index - 1)
        end = min(len(lines), index + 8)

        for i in range(start, end):
            context_parts.append(lines[i])

        context = "\n".join(context_parts)

        sizes = find_sizes(context)
        surfaces = find_surface(context)
        textures = find_texture(context)

        # ----------------------------------------------------
        # HARD EVIDENCE RULE
        # ----------------------------------------------------

        if not sizes:
            continue

        if not surfaces and not textures:
            continue

        candidates.append({
            "productName": name,
            "application": application,
            "size": sizes,
            "finish": surfaces,
            "texture": textures,
            "lineIndex": index
        })

    return candidates


# ============================================================
# DEDUP LIST
# ============================================================
def unique_list(values):
    """
    Safely return unique values as a list.

    Handles:
    - None
    - string
    - list
    - tuple
    - integer
    """

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

        # Keep page numbers numeric
        if isinstance(value, int):
            if value not in result:
                result.append(value)
            continue

        value = str(value).strip()

        if not value:
            continue

        if value not in result:
            result.append(value)

    return result



# ============================================================
# PRODUCT KEY
# ============================================================

def product_key(product):
    name = normalize_line(
        product.get("productName", "")
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
                    product.get("productName"),

                "category":
                    product.get("category"),

                "collection":
                    product.get("collection"),

                "size":
                    unique_list(
                        product.get("size")
                    ),

                "finish":
                    unique_list(
                        product.get("finish")
                    ),

                "texture":
                    unique_list(
                        product.get("texture")
                    ),

                "application":
                    unique_list(
                        product.get("application")
                    ),

                "color":
                    product.get("color"),

                "design":
                    unique_list(
                        product.get("design")
                    ),

                "image":
                    None,

                "images":
                    [],

                # IMPORTANT:
                # page numbers remain integers
                "pages":
                    [
                        int(page)
                        for page in
                        unique_list(
                            product.get("pages")
                        )
                        if str(page).isdigit()
                    ]
            }

            continue

        existing = merged[key]

        # ----------------------------------------------------
        # SIZE
        # ----------------------------------------------------

        existing["size"] = unique_list(
            list(existing.get("size") or [])
            + list(product.get("size") or [])
        )

        # ----------------------------------------------------
        # FINISH
        # ----------------------------------------------------

        existing["finish"] = unique_list(
            list(existing.get("finish") or [])
            + list(product.get("finish") or [])
        )

        # ----------------------------------------------------
        # TEXTURE
        # ----------------------------------------------------

        existing["texture"] = unique_list(
            list(existing.get("texture") or [])
            + list(product.get("texture") or [])
        )

        # ----------------------------------------------------
        # APPLICATION
        # ----------------------------------------------------

        existing["application"] = unique_list(
            list(existing.get("application") or [])
            + list(product.get("application") or [])
        )

        # ----------------------------------------------------
        # DESIGN
        # ----------------------------------------------------

        existing["design"] = unique_list(
            list(existing.get("design") or [])
            + list(product.get("design") or [])
        )

        # ----------------------------------------------------
        # PAGES
        # ----------------------------------------------------

        old_pages = []

        for page in existing.get("pages") or []:
            try:
                old_pages.append(int(page))
            except:
                pass

        new_pages = []

        for page in product.get("pages") or []:
            try:
                new_pages.append(int(page))
            except:
                pass

        existing["pages"] = sorted(
            set(old_pages + new_pages)
        )

        # ----------------------------------------------------
        # CATEGORY
        # ----------------------------------------------------

        if not existing.get("category"):
            existing["category"] = product.get(
                "category"
            )

        # ----------------------------------------------------
        # COLLECTION
        # ----------------------------------------------------

        if not existing.get("collection"):
            existing["collection"] = product.get(
                "collection"
            )

    return list(
        merged.values()
    )
    
def extract_products_from_pdf(reader):

    detected = []

    for page_number, page in enumerate(
        reader.pages,
        start=1
    ):

        try:

            page_text = (
                page.extract_text()
                or ""
            )

            page_text = normalize_text(
                page_text
            )

            if not page_text:
                continue

            candidates = parse_detail_blocks(
                page_text
            )

            if not candidates:
                continue

            category = find_category(
                page_text
            )

            collection = find_collection(
                page_text
            )

            for candidate in candidates:

                name = candidate[
                    "productName"
                ]

                # --------------------------------------------
                # Candidate must have real metadata evidence
                # --------------------------------------------

                if not candidate.get("size"):
                    continue

                if (
                    not candidate.get("finish")
                    and not candidate.get("texture")
                ):
                    continue

                detected.append({

                    "productName":
                        name,

                    "category":
                        category,

                    "collection":
                        collection,

                    "size":
                        candidate.get("size"),

                    "finish":
                        candidate.get("finish"),

                    "texture":
                        candidate.get("texture"),

                    "application":
                        candidate.get("application"),

                    "color":
                        name,

                    "design":
                        candidate.get("texture"),

                    "image":
                        None,

                    "images":
                        [],

                    "pages":
                        [page_number]
                })

        except Exception as error:

            print(
                f"Page {page_number} "
                f"product extraction error: "
                f"{error}"
            )

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

        # Reject microscopic decorative assets
        if width < 100 or height < 100:
            return False

        # Reject extremely thin lines/icons
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
# EXTRACT PAGE IMAGES
# ============================================================

def extract_page_images(
    doc,
    page_number,
    output_dir
):

    page = doc[
        page_number - 1
    ]

    images = []

    try:

        image_list = page.get_images(
            full=True
        )

        seen_hashes = set()

        for image_index, image_info in enumerate(
            image_list,
            start=1
        ):

            try:

                xref = image_info[0]

                base = doc.extract_image(
                    xref
                )

                image_data = base.get(
                    "image"
                )

                if not valid_image_bytes(
                    image_data
                ):
                    continue

                digest = image_hash(
                    image_data
                )

                if digest in seen_hashes:
                    continue

                seen_hashes.add(
                    digest
                )

                extension = base.get(
                    "ext",
                    "png"
                )

                image_name = (
                    f"page-{page_number}"
                    f"-image-{image_index}."
                    f"{extension}"
                )

                image_path = os.path.join(
                    output_dir,
                    image_name
                )

                with open(
                    image_path,
                    "wb"
                ) as output:

                    output.write(
                        image_data
                    )

                images.append({

                    "page":
                        page_number,

                    "image":
                        image_name,

                    "path":
                        image_path,

                    "width":
                        base.get(
                            "width"
                        ),

                    "height":
                        base.get(
                            "height"
                        ),

                    "xref":
                        xref
                })

            except Exception as image_error:

                print(
                    f"Image extraction failed "
                    f"page={page_number}, "
                    f"image={image_index}: "
                    f"{image_error}"
                )

    except Exception as error:

        print(
            f"Page image listing failed "
            f"page={page_number}: "
            f"{error}"
        )

    return images


# ============================================================
# PRODUCT NAME SEARCH RECT
# ============================================================

def find_product_rects(
    page,
    product_name
):

    rects = []

    try:

        # Direct search
        rects = page.search_for(
            product_name
        )

        if rects:
            return rects

        # Case-insensitive manual block search
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

        # ----------------------------------------------------
        # Use detail pages only
        # ----------------------------------------------------

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

            # ------------------------------------------------
            # Choose first sensible occurrence
            # ------------------------------------------------

            rect = rects[0]

            page_width = page.rect.width
            page_height = page.rect.height

            # ------------------------------------------------
            # IMPORTANT:
            #
            # We do NOT crop the whole page.
            # We crop the visual area around the
            # product-detail occurrence.
            #
            # Keep enough surrounding area to retain
            # actual tile/product visual.
            # ------------------------------------------------

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
                rect.y1 + 120
            )

            crop_rect = pymupdf.Rect(
                crop_left,
                crop_top,
                crop_right,
                crop_bottom
            )

            # Avoid absurdly tiny crops
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

    try:

        doc = pymupdf.open(
            stream=pdf_bytes,
            filetype="pdf"
        )

        for product in products:

            product = crop_product_image(
                doc,
                product,
                filename
            )

        doc.close()

    except Exception as error:

        print(
            "Product image mapping error:",
            error
        )

    return products


# ============================================================
# FINAL CLEAN PRODUCT
# ============================================================

def clean_product(product):

    return {

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
            product.get(
                "size"
            ) or None,

        "finish":
            product.get(
                "finish"
            ) or None,

        "texture":
            product.get(
                "texture"
            ) or None,

        "application":
            product.get(
                "application"
            ) or None,

        "color":
            product.get(
                "color"
            ),

        "design":
            product.get(
                "design"
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
            product.get(
                "pages"
            ) or []
    }


# ============================================================
# PDF EXTRACTION API
# ============================================================

@app.post("/extract")
async def extract_pdf(
    file: UploadFile = File(...)
):

    # --------------------------------------------------------
    # Validate filename/content
    # --------------------------------------------------------

    filename = file.filename or "document.pdf"

    if not filename.lower().endswith(
        ".pdf"
    ):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are allowed"
        )

    try:

        # ----------------------------------------------------
        # Read bytes
        # ----------------------------------------------------

        pdf_bytes = await file.read()

        if not pdf_bytes:

            raise HTTPException(
                status_code=400,
                detail="Empty PDF file"
            )

        # ----------------------------------------------------
        # Open PDF
        # ----------------------------------------------------

        reader = PdfReader(
            io.BytesIO(
                pdf_bytes
            )
        )

        pages = len(
            reader.pages
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
                    f"page {page_number}: "
                    f"{page_error}"
                )

        full_text = normalize_text(
            "\n".join(
                all_text
            )
        )

        # ----------------------------------------------------
        # Product extraction
        # ----------------------------------------------------

        products = extract_products_from_pdf(
            reader
        )

        # ----------------------------------------------------
        # Product images
        # ----------------------------------------------------

        products = map_product_images(
            products,
            pdf_bytes,
            filename
        )

        # ----------------------------------------------------
        # Clean response
        # ----------------------------------------------------

        clean_products = [
            clean_product(product)
            for product in products
        ]

        return {

            "success":
                True,

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