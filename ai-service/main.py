from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image
import pymupdf
import os
import io
import sys
import re
import hashlib
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

CODE_REGEX = re.compile(
    r"\b([A-Z]{1,3}\d{4,8}(?:-[A-Z0-9]+)?|[A-Z]{2,5}-\d{3,6})\b"
)

PRICE_REGEX = re.compile(
    r"(?:₹|Rs\.?|INR)\s*([\d,]+(?:\.\d{2})?)",
    re.IGNORECASE
)

SIZE_REGEX = re.compile(
    r"\b(\d{2,4}\s*[x×X*]\s*\d{2,4}(?:\s*[x×X*]\s*\d{2,4})?\s*(?:mm|cm)?)\b",
    re.IGNORECASE
)

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
    dir_path = os.path.join("extracted_images", safe_doc_name, "product_crops")
    os.makedirs(dir_path, exist_ok=True)
    return dir_path


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

        image_name = f"{prefix}.{image_ext}"
        image_path = os.path.join(output_dir, image_name)
        with open(image_path, "wb") as f:
            f.write(image_bytes)

        return f"extracted_images/{safe_doc_name}/product_crops/{image_name}"
    except Exception as e:
        return None


def crop_image_from_bbox(page: pymupdf.Page, bbox: List[float], output_dir: str, safe_doc_name: str, prefix: str) -> Optional[str]:
    try:
        crop_rect = pymupdf.Rect(bbox[0] - 5, bbox[1] - 5, bbox[2] + 5, bbox[3] + 5)
        if crop_rect.width < 25 or crop_rect.height < 25:
            return None

        pix = page.get_pixmap(
            matrix=pymupdf.Matrix(2.5, 2.5),
            clip=crop_rect,
            alpha=False
        )

        image_name = f"{prefix}.png"
        image_path = os.path.join(output_dir, image_name)
        pix.save(image_path)

        return f"extracted_images/{safe_doc_name}/product_crops/{image_name}"
    except Exception as e:
        return None


# ============================================================
# SPATIAL CATALOG PARSER
# ============================================================

def parse_catalog_document(doc: pymupdf.Document, filename: str) -> List[Dict[str, Any]]:
    safe_doc = clean_doc_name(filename)
    output_dir = get_images_output_dir(safe_doc)
    
    products = []
    current_collection = "General Collection"
    current_category = "Ceramic & Bathware"
    
    total_pages = len(doc)
    
    for page_idx in range(total_pages):
        page = doc[page_idx]
        page_num = page_idx + 1
        
        words = page.get_text("words")
        blocks = page.get_text("blocks")
        
        # 1. Update Collection & Category from page headers
        for b in blocks:
            b_text = normalize_text(b[4])
            if "COLLECTION" in b_text.upper():
                coll_m = re.sub(r"\s*COLLECTION\s*", "", b_text, flags=re.IGNORECASE).strip()
                if 2 < len(coll_m) < 40 and not any(w in coll_m.upper() for w in ["BATHWARE", "PRICE", "2026", "2025"]):
                    current_collection = coll_m
            for cat_keyword in ["KITCHEN FAUCET", "BASIN MIXER", "WALL MIXER", "BATH SPOUT", "BIB TAP", "PILLAR", "UPPER TRIM", "ANGLE VALVE", "SHOWER", "SANITARYWARE", "FULLBODY", "VITRIFIED"]:
                if cat_keyword in b_text.upper():
                    current_category = cat_keyword.title()
                    
        # 2. Extract Valid Product Photos on Page (filter out swatches / icons / sidebars)
        page_images = page.get_image_info(xrefs=True)
        valid_images = []
        for img in page_images:
            bbox = img.get("bbox")
            width = bbox[2] - bbox[0]
            height = bbox[3] - bbox[1]
            if width >= 25 and height >= 25 and width < page.rect.width * 0.85 and height < page.rect.height * 0.85:
                valid_images.append({
                    "xref": img.get("xref"),
                    "bbox": bbox,
                    "x_center": (bbox[0] + bbox[2]) / 2,
                    "y_top": bbox[1],
                    "y_bottom": bbox[3],
                    "width": width,
                    "height": height
                })
                
        # 3. Extract all Prices with bounding boxes
        page_prices = []
        for b in blocks:
            b_text = normalize_text(b[4])
            for line in b_text.split("\n"):
                p_match = PRICE_REGEX.search(line)
                if p_match:
                    page_prices.append({
                        "price": f"₹ {p_match.group(1)}",
                        "x_center": (b[0] + b[2]) / 2,
                        "y_center": (b[1] + b[3]) / 2,
                        "bbox": (b[0], b[1], b[2], b[3])
                    })
                    
        # 4. Extract all Titles with bounding boxes
        page_titles = []
        for b in blocks:
            b_text = normalize_text(b[4])
            if not CODE_REGEX.search(b_text) and not PRICE_REGEX.search(b_text):
                if 3 < len(b_text) < 70 and not any(w in b_text.upper() for w in ["COLLECTION", "BATHWARE", "PRICE LIST", "PAGE"]):
                    # Don't include single finish words like "Chrome" as title
                    if b_text.lower() not in FINISH_MAP:
                        page_titles.append({
                            "text": b_text.replace("\n", " "),
                            "x_center": (b[0] + b[2]) / 2,
                            "y_top": b[1],
                            "y_bottom": b[3]
                        })
                        
        # 5. Extract Product Codes & Perform Spatial Row Matching
        page_codes = []
        for w in words:
            m = CODE_REGEX.search(w[4])
            if m:
                page_codes.append({
                    "code": m.group(1),
                    "x0": w[0],
                    "y0": w[1],
                    "x1": w[2],
                    "y1": w[3],
                    "x_center": (w[0] + w[2]) / 2,
                    "y_center": (w[1] + w[3]) / 2
                })
                
        page_extracted_count = 0
        
        # METHOD A: Extract Code-Driven Products (Faucets, Fittings, Bathware, Sanitaryware)
        for c in page_codes:
            code_str = c["code"]
            cx = c["x_center"]
            cy = c["y_center"]
            
            # --- Match Price ---
            matched_price = None
            best_price_dist = 9999
            for p in page_prices:
                # Same row (vertical distance within 22px) and horizontally nearby to right/center
                if abs(p["y_center"] - cy) < 22 and p["x_center"] >= cx - 35 and p["x_center"] <= cx + 180:
                    dist = abs(p["y_center"] - cy) + abs(p["x_center"] - cx) * 0.1
                    if dist < best_price_dist:
                        best_price_dist = dist
                        matched_price = p["price"]
                        
            # --- Match Color / Finish ---
            finish = "Chrome"
            if "-GM" in code_str: finish = "Gun Metal"
            elif "-RG" in code_str: finish = "Rose Gold"
            elif "-MB" in code_str or "-BK" in code_str: finish = "Matt Black"
            elif "-FG" in code_str: finish = "French Gold"
            elif "-WH" in code_str: finish = "White"
            else:
                # Check words on the same row to the left
                for w in words:
                    if abs(w[1] - cy) < 16 and w[0] < cx and w[0] > cx - 130:
                        for k, val in FINISH_MAP.items():
                            if k == w[4].lower() or k in w[4].lower():
                                finish = val
                                break
                                
            # --- Match Title ---
            matched_title = ""
            best_title_dist = 9999
            for t in page_titles:
                # Located above the code table (up to 180px above) and in similar column
                if t["y_bottom"] <= cy + 12 and t["y_bottom"] >= cy - 180:
                    if abs(t["x_center"] - cx) < 130:
                        dist = cy - t["y_bottom"]
                        if dist < best_title_dist:
                            best_title_dist = dist
                            matched_title = t["text"]
                            
            # --- Match Product Photo ---
            # The product photo is located directly above the title or code table in the column
            matched_img = None
            best_img_dist = 9999
            for img in valid_images:
                if img["y_bottom"] <= cy + 20 and img["y_bottom"] >= cy - 320:
                    if abs(img["x_center"] - cx) < 120:
                        dist = cy - img["y_bottom"]
                        if dist < best_img_dist:
                            best_img_dist = dist
                            matched_img = img
                            
            # Save Image
            img_rel_path = None
            if matched_img:
                safe_code = re.sub(r"[^a-zA-Z0-9_-]", "_", code_str)
                if matched_img.get("xref"):
                    img_rel_path = save_image_from_xref(
                        doc, matched_img["xref"], output_dir, safe_doc,
                        f"p{page_num}-{safe_code}"
                    )
                if not img_rel_path:
                    img_rel_path = crop_image_from_bbox(
                        page, matched_img["bbox"], output_dir, safe_doc,
                        f"p{page_num}-{safe_code}"
                    )

            p_title = matched_title if matched_title else (f"{current_category} ({code_str})" if current_category else f"Product {code_str}")
            
            products.append({
                "productCode": code_str,
                "productName": p_title,
                "category": current_category,
                "collection": current_collection,
                "size": None,
                "finish": [finish],
                "color": finish,
                "price": matched_price,
                "image": img_rel_path,
                "pages": [page_num]
            })
            page_extracted_count += 1

        # METHOD B: Extract Ceramic & Vitrified Tiles (Named tiles like RIVER GREY with sizes & finishes)
        for b in blocks:
            b_text = normalize_text(b[4])
            found_sizes = SIZE_REGEX.findall(b_text)
            found_finishes = [val for k, val in FINISH_MAP.items() if re.search(rf"\b{re.escape(k)}\b", b_text, re.IGNORECASE)]
            
            if found_sizes or (found_finishes and any(f in found_finishes for f in ["Polished", "Matt", "Glossy", "Carving", "Protect", "Rocker"])):
                b_lines = [l.strip() for l in b_text.split("\n") if l.strip()]
                for line in b_lines:
                    if 3 <= len(line) <= 40 and re.match(r"^[A-Za-z][A-Za-z0-9\s'-]+$", line):
                        line_lower = line.lower()
                        if not any(w in line_lower for w in ["collection", "catalogue", "simpolo", "somany", "kajaria", "page", "table", "price", "bathware", "specification", "chrome", "finish", "size", "texture"]):
                            # Crop tile preview image
                            b_rect = pymupdf.Rect(b[0], b[1], b[2], b[3])
                            safe_line = re.sub(r"[^a-zA-Z0-9_-]", "_", line)
                            
                            # Check if photo above tile block
                            tile_img_path = None
                            for img in valid_images:
                                if img["y_bottom"] <= b_rect.y0 + 20 and abs(img["x_center"] - (b[0]+b[2])/2) < 120:
                                    tile_img_path = save_image_from_xref(doc, img["xref"], output_dir, safe_doc, f"p{page_num}-tile-{safe_line}")
                                    break
                            if not tile_img_path:
                                tile_img_path = crop_image_from_bbox(page, [b[0]-20, b[1]-150, b[2]+20, b[1]], output_dir, safe_doc, f"p{page_num}-tile-{safe_line}")
                                
                            products.append({
                                "productCode": None,
                                "productName": line,
                                "category": "Ceramic & Vitrified Tiles",
                                "collection": current_collection or "Tiles Collection",
                                "size": unique_list([s.replace("×", "x").replace(" ", "") for s in found_sizes]) if found_sizes else None,
                                "finish": found_finishes if found_finishes else ["Polished"],
                                "color": found_finishes[0] if found_finishes else "Standard",
                                "price": None,
                                "image": tile_img_path,
                                "pages": [page_num]
                            })
                            page_extracted_count += 1
                            break

        # METHOD C: Scanned / Image-Only Catalogs (e.g. Sanitaryware catalogs without text layers)
        if page_extracted_count == 0 and valid_images:
            for img_idx, img_info in enumerate(valid_images[:6]):
                img_path = save_image_from_xref(
                    doc, img_info["xref"], output_dir, safe_doc,
                    f"p{page_num}-item-{img_idx+1}"
                )
                if not img_path:
                    img_path = crop_image_from_bbox(
                        page, img_info["bbox"], output_dir, safe_doc,
                        f"p{page_num}-item-{img_idx+1}"
                    )
                if img_path:
                    products.append({
                        "productCode": f"CAT-{page_num}-{img_idx+1}",
                        "productName": f"{current_collection} Item {page_num}-{img_idx+1}" if current_collection != "General Collection" else f"Sanitaryware Item {page_num}-{img_idx+1}",
                        "category": current_category if current_category != "Ceramic & Bathware" else "Sanitaryware",
                        "collection": current_collection,
                        "size": None,
                        "finish": ["Glossy White"],
                        "color": "White",
                        "price": None,
                        "image": img_path,
                        "pages": [page_num]
                    })

    # Deduplicate & Merge Products
    deduped = {}
    for p in products:
        code_part = p.get("productCode") or ""
        name_part = p.get("productName") or ""
        key = f"{code_part}::{name_part}".strip().lower()
        if not key or key == "::":
            continue
            
        if key in deduped:
            existing = deduped[key]
            if p.get("finish"):
                existing["finish"] = unique_list((existing.get("finish") or []) + p["finish"])
            if p.get("size"):
                existing["size"] = unique_list((existing.get("size") or []) + p["size"])
            if not existing.get("image") and p.get("image"):
                existing["image"] = p["image"]
            if not existing.get("price") and p.get("price"):
                existing["price"] = p["price"]
            if p.get("pages"):
                existing["pages"] = unique_list(existing.get("pages", []) + p["pages"])
        else:
            deduped[key] = p

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