import argparse
import json
import os
from typing import Any, Dict, List, Optional

import pymupdf

import main


def page_text_lines(page: pymupdf.Page) -> List[Dict[str, Any]]:
    lines = main.text_lines_from_page(page)
    text = " ".join(line["text"] for line in lines)
    if sum(char.isalpha() for char in text) < 40 and page.get_images():
        ocr_lines = main.ocr_page_lines(page)
        ocr_text = " ".join(line["text"] for line in ocr_lines)
        if len(ocr_text) > len(text):
            return ocr_lines
    return lines


def eligible_images(page: pymupdf.Page, candidates: List[Dict[str, Any]], lines: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return main.eligible_image_placements(page, candidates, lines)


def candidate_image_matches(candidate: Dict[str, Any], images: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    matches = []
    for image_index, image in enumerate(images):
        distance = main.image_distance_to_candidate(image["bbox"], candidate["bbox"])
        if distance is not None:
            matches.append({
                "imageIndex": image_index,
                "xref": image.get("xref"),
                "bbox": [round(value, 1) for value in image["bbox"]],
                "verticalGap": round(distance, 1),
            })
    return matches


def product_candidate_key(product: Dict[str, Any]) -> tuple:
    return tuple(product.get(field) for field in ("productCode", "productName", "size", "surface", "finish"))


def build_report(pdf_path: str, display_name: Optional[str] = None) -> Dict[str, Any]:
    filename = os.path.basename(pdf_path)
    source_file = display_name or filename
    doc = pymupdf.open(pdf_path)
    try:
        products = main.parse_catalog_document(doc, filename)
        pages = {}
        for page_index, page in enumerate(doc):
            page_num = page_index + 1
            lines = page_text_lines(page)
            page_text = " ".join(line["text"] for line in lines)
            candidates = main.extract_product_records(lines, page_text, filename, page_num)
            images = eligible_images(page, candidates, lines)
            selected = []
            candidate_matches = []
            for candidate in candidates:
                matches = candidate_image_matches(candidate, images)
                candidate_matches.append(matches)
                best_match = min(matches, key=lambda match: (match["verticalGap"], match["imageIndex"])) if matches else None
                selected.append(best_match["imageIndex"] if best_match else None)
            image_usage = {
                image_index: selected.count(image_index)
                for image_index in set(selected)
                if image_index is not None
            }
            image_cells = main.aligned_image_cells(candidates, selected, images, lines)
            pages[page_num] = {
                "pageHasImagePlacements": bool(page.get_image_info(xrefs=True)),
                "pageImagePlacementCount": len(page.get_image_info(xrefs=True)),
                "eligibleImagePlacementCount": len(images),
                "candidates": candidates,
                "candidateMatches": candidate_matches,
                "selectedImageIndexes": selected,
                "imageUsage": image_usage,
                "alignedImageCells": image_cells,
            }

        audited = []
        for product in products:
            page_num = product["sourcePage"]
            page_audit = pages[page_num]
            candidate_index = next((
                index for index, candidate in enumerate(page_audit["candidates"])
                if product_candidate_key(product) == (
                    candidate.get("code"), candidate.get("name"), candidate.get("size"),
                    candidate.get("surface"), candidate.get("finish"),
                )
            ), None)
            candidate = page_audit["candidates"][candidate_index] if candidate_index is not None else None
            matches = page_audit["candidateMatches"][candidate_index] if candidate_index is not None else []
            selected_index = page_audit["selectedImageIndexes"][candidate_index] if candidate_index is not None else None
            image = None
            image_bbox = None
            crop_bbox = None
            reason = "No matching parser candidate was found for this final product record"

            if candidate is not None and selected_index is None:
                if not page_audit["eligibleImagePlacementCount"] and not page_audit["pageHasImagePlacements"]:
                    reason = "The PDF page contains no embedded image placements"
                elif not page_audit["eligibleImagePlacementCount"]:
                    reason = "Image placements are present, but none meets the minimum dimensions and product-layout evidence checks"
                else:
                    reason = "Images are present, but none overlap the product text horizontally within 180 points vertically"
            elif candidate is not None and selected_index is not None:
                if page_audit["imageUsage"][selected_index] == 1:
                    image = page_audit["eligibleImagePlacementCount"] and eligible_images(doc[page_num - 1], page_audit["candidates"], page_text_lines(doc[page_num - 1]))[selected_index]
                    image_bbox = [round(value, 1) for value in image["bbox"]]
                    reason = "Unique same-page image placement overlaps the label horizontally and is within the vertical association limit"
                elif candidate_index in page_audit["alignedImageCells"]:
                    image = eligible_images(doc[page_num - 1], page_audit["candidates"], page_text_lines(doc[page_num - 1]))[selected_index]
                    image_bbox = [round(value, 1) for value in image["bbox"]]
                    crop_bbox = [round(value, 1) for value in page_audit["alignedImageCells"][candidate_index]]
                    reason = "Crop is restricted to the candidate's same-row column cell within a shared composite image"
                else:
                    image = eligible_images(doc[page_num - 1], page_audit["candidates"], page_text_lines(doc[page_num - 1]))[selected_index]
                    image_bbox = [round(value, 1) for value in image["bbox"]]
                    reason = "Shared composite image is ambiguous: product labels do not form validated, regular same-row columns"

            image_path = product.get("image")
            absolute_image_path = os.path.join(os.path.dirname(__file__), image_path) if image_path else None
            image_file_valid = False
            image_file_size = None
            image_dimensions = None
            image_format = None
            if absolute_image_path and os.path.isfile(absolute_image_path):
                try:
                    with main.Image.open(absolute_image_path) as image_file:
                        image_width, image_height = image_file.size
                        image_format = image_file.format
                        image_file.verify()
                    image_file_valid = image_width > 0 and image_height > 0 and os.path.getsize(absolute_image_path) > 0
                    image_file_size = os.path.getsize(absolute_image_path)
                    image_dimensions = [image_width, image_height]
                except (OSError, ValueError):
                    pass
            audited.append({
                **product,
                "sourceFile": source_file,
                "pdfPageHasImagePlacements": page_audit["pageHasImagePlacements"],
                "pdfPageImagePlacementCount": page_audit["pageImagePlacementCount"],
                "eligibleImagePlacementCount": page_audit["eligibleImagePlacementCount"],
                "candidateImageCount": len(matches),
                "productTextBbox": [round(value, 1) for value in candidate["bbox"]] if candidate else None,
                "candidateImages": matches,
                "assignedImageXref": image.get("xref") if image else None,
                "assignedImageBbox": image_bbox,
                "assignedCropBbox": crop_bbox,
                "associationReason": reason,
                "imageFileExists": bool(absolute_image_path and os.path.isfile(absolute_image_path)),
                "imageFileValid": image_file_valid,
                "imageFileSizeBytes": image_file_size,
                "imageDimensions": image_dimensions,
                "imageFormat": image_format,
            })

        with_images = sum(bool(product["image"]) for product in audited)
        missing_products = [product for product in audited if not product["image"]]
        image_paths = [product["image"] for product in audited if product["image"]]
        image_filenames = [os.path.basename(image_path) for image_path in image_paths]
        duplicate_paths = len(image_paths) - len(set(image_paths))
        duplicate_filenames = len(image_filenames) - len(set(image_filenames))
        missing_source_images = [
            product for product in missing_products
            if not product["pdfPageHasImagePlacements"]
        ]
        matching_failures = [
            product for product in missing_products
            if product["candidateImageCount"] > 0
        ]
        crop_failures = [
            product for product in missing_products
            if product["assignedImageXref"] is not None
        ]
        extraction_failures = [
            product for product in audited
            if product["image"] and (not product["imageFileExists"] or not product["imageFileValid"])
        ]
        return {
            "sourceFile": source_file,
            "totalPages": len(doc),
            "totalProducts": len(audited),
            "productsWithImage": with_images,
            "productsWithImageNull": len(audited) - with_images,
            "imageCoveragePercent": round(with_images / len(audited) * 100, 1) if audited else 0,
            "auditTotals": {
                "validImageFiles": sum(product["imageFileValid"] for product in audited),
                "missingSourceImages": len(missing_source_images),
                "extractionFailures": len(extraction_failures),
                "matchingFailures": len(matching_failures),
                "cropFailures": len(crop_failures),
                "missingFiles": sum(bool(product["image"]) and not product["imageFileExists"] for product in audited),
                "invalidFiles": sum(bool(product["image"]) and not product["imageFileValid"] for product in audited),
                "duplicateImagePaths": duplicate_paths,
                "duplicateFilenames": duplicate_filenames,
                "unexplainedMissingImages": len(missing_products) - len(missing_source_images) - len(matching_failures),
            },
            "missingImageProducts": [
                {
                    "productName": product["productName"],
                    "productCode": product["productCode"],
                    "size": product["size"],
                    "surface": product["surface"],
                    "finish": product["finish"],
                    "collection": product["collection"],
                    "sourceFile": product["sourceFile"],
                    "sourcePage": product["sourcePage"],
                    "reason": product["associationReason"],
                }
                for product in missing_products
            ],
            "products": audited,
        }
    finally:
        doc.close()


def main_cli() -> None:
    parser = argparse.ArgumentParser(description="Audit PDF product-image associations")
    parser.add_argument("pdf", help="Path to the PDF to audit")
    parser.add_argument("--source-name", help="Display/source filename to record in the report")
    parser.add_argument("--output", default="image-audit-report.json", help="Output JSON report path")
    args = parser.parse_args()

    report = build_report(args.pdf, args.source_name)
    with open(args.output, "w", encoding="utf-8") as report_file:
        json.dump(report, report_file, indent=2, ensure_ascii=False)
        report_file.write("\n")
    print(f"Wrote {args.output}: {report['totalProducts']} products, {report['productsWithImage']} images ({report['imageCoveragePercent']}% coverage)")


if __name__ == "__main__":
    main_cli()