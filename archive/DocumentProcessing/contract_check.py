import os
import cv2
import numpy as np
from pypdf import PdfReader
from pdf2image import convert_from_path

def extract_annotations(pdf_path):
    """
    Extracts text-based annotations, comments, and form field changes 
    made to the PDF.
    """
    reader = PdfReader(pdf_path)
    annotations = []
    
    for page_num, page in enumerate(reader.pages):
        if "/Annots" in page:
            for annot in page["/Annots"]:
                obj = annot.get_object()
                annot_data = {
                    "page": page_num + 1,
                    "type": obj.get("/Subtype", "Unknown"),
                    "author": obj.get("/T", "Unknown"),
                    "contents": obj.get("/Contents", ""),
                }
                annotations.append(annot_data)
    return annotations

def detect_visual_changes(base_img, target_img, threshold=30):
    """
    Compares two images pixel-by-pixel to find visual edits, 
    returning a mask of differences.
    """
    # Ensure images are the same size
    if base_img.shape != target_img.shape:
        target_img = cv2.resize(target_img, (base_img.shape[1], base_img.shape[0]))
        
    # Compute absolute difference
    diff = cv2.absdiff(base_img, target_img)
    gray_diff = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
    
    # Threshold the difference to get a clean binary mask
    _, thresh = cv2.threshold(gray_diff, threshold, 255, cv2.THRESH_BINARY)
    return thresh

def look_for_signature(image):
    """
    A basic heuristic to look for a signature in an image block.
    Real-world uses often look for blue/black ink or non-uniform text clusters
    in the bottom 25% of a document.
    """
    # Convert to grayscale and threshold
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)
    
    # Focus on the bottom portion of the document where signatures usually live
    h, w = thresh.shape
    bottom_crop = thresh[int(h*0.75):h, :]
    
    # Find contours (shapes) in the bottom crop
    contours, _ = cv2.findContours(bottom_crop, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    for cnt in contours:
        x, y, cw, ch = cv2.boundingRect(cnt)
        aspect_ratio = float(cw) / ch
        # Signatures are usually wider than they are tall, and have a decent area
        if cw > 80 and ch > 20 and aspect_ratio > 2.0:
            return True, (x, y + int(h*0.75), cw, ch)
            
    return False, None

def process_pdf_comparison(base_pdf_path, comparison_pdf_path, output_dir="output"):
    os.makedirs(output_dir, exist_ok=True)
    
    print("--- Step 1: Extracting Programmatic Annotations ---")
    annots = extract_annotations(comparison_pdf_path)
    for a in annots:
        print(f"[Page {a['page']}] {a['type']} by {a['author']}: '{a['contents']}'")

    print("\n--- Step 2: Converting PDFs to Images for Visual Comparison ---")
    base_pages = convert_from_path(base_pdf_path)
    comp_pages = convert_from_path(comparison_pdf_path)
    
    for i, (base_page, comp_page) in enumerate(zip(base_pages, comp_pages)):
        page_num = i + 1
        
        # Convert PIL images to OpenCV format (BGR)
        base_img = cv2.cvtColor(np.array(base_page), cv2.COLOR_RGB2BGR)
        comp_img = cv2.cvtColor(np.array(comp_page), cv2.COLOR_RGB2BGR)
        
        # Detect visual changes
        diff_mask = detect_visual_changes(base_img, comp_img)
        change_pixels = np.sum(diff_mask == 255)
        
        if change_pixels > 100:  # Ignore tiny noise artifacts
            print(f"[Page {page_num}] Visual changes detected ({change_pixels} pixels modified).")
            # Save a visual diff file highlighting the changes in red
            highlight_img = comp_img.copy()
            highlight_img[diff_mask == 255] = [0, 0, 255] 
            cv2.imwrite(f"{output_dir}/page_{page_num}_diff.png", highlight_img)
            
        # Check for signature
        has_sig, bbox = look_for_signature(comp_img)
        if has_sig:
            print(f"[Page {page_num}] Possible signature or stamp detected in the bottom region!")
            # Draw a green box around the signature area
            x, y, w, h = bbox
            cv2.rectangle(comp_img, (x, y), (x + w, y + h), (0, 255, 0), 3)
            cv2.imwrite(f"{output_dir}/page_{page_num}_signature.png", comp_img)

# Example Usage:
# process_pdf_comparison("baseline.pdf", "signed_and_edited.pdf")
