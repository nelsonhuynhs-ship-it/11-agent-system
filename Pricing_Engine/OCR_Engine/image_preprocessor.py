# -*- coding: utf-8 -*-
"""
Image Preprocessor for OCR
Prepares pricing images for better OCR accuracy
"""

import cv2
import numpy as np
import os
import sys


def preprocess_for_ocr(image_path, output_path=None):
    """
    Preprocess image for better OCR accuracy
    
    Steps:
    1. Resize to reasonable size
    2. Convert to grayscale
    3. Apply adaptive threshold
    4. Denoise
    """
    
    print(f"[1/5] Loading image: {os.path.basename(image_path)}")
    
    # Load image
    img = cv2.imread(image_path)
    if img is None:
        print(f"Error: Cannot load image {image_path}")
        return None
    
    original_size = os.path.getsize(image_path) / 1024 / 1024
    height, width = img.shape[:2]
    print(f"      Original: {width}x{height}, {original_size:.1f}MB")
    
    # Step 1: Resize to reasonable size
    print(f"[2/5] Resizing...")
    max_width = 2000
    if width > max_width:
        scale = max_width / width
        img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        height, width = img.shape[:2]
        print(f"      Resized to: {width}x{height}")
    
    # Step 2: Convert to grayscale
    print(f"[3/5] Converting to grayscale...")
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Step 3: Apply adaptive threshold for better contrast
    print(f"[4/5] Enhancing contrast...")
    # Use adaptive threshold for documents
    binary = cv2.adaptiveThreshold(
        gray, 255, 
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
        cv2.THRESH_BINARY, 
        11, 2
    )
    
    # Step 4: Denoise
    print(f"[5/5] Denoising...")
    denoised = cv2.fastNlMeansDenoising(binary, None, 10, 7, 21)
    
    # Generate output path if not provided
    if output_path is None:
        base, ext = os.path.splitext(image_path)
        output_path = f"{base}_preprocessed.png"
    
    # Save preprocessed image
    cv2.imwrite(output_path, denoised)
    
    new_size = os.path.getsize(output_path) / 1024 / 1024
    print(f"\n[OK] Saved: {output_path}")
    print(f"     Size: {original_size:.1f}MB -> {new_size:.1f}MB ({new_size/original_size*100:.0f}%)")
    
    return output_path


def preprocess_keep_color(image_path, output_path=None):
    """
    Alternative: Preprocess but keep some color info
    Better for tables with colored backgrounds
    """
    
    print(f"[1/4] Loading image: {os.path.basename(image_path)}")
    
    img = cv2.imread(image_path)
    if img is None:
        print(f"Error: Cannot load image {image_path}")
        return None
    
    original_size = os.path.getsize(image_path) / 1024 / 1024
    height, width = img.shape[:2]
    print(f"      Original: {width}x{height}, {original_size:.1f}MB")
    
    # Step 1: Resize
    print(f"[2/4] Resizing...")
    max_width = 1500
    if width > max_width:
        scale = max_width / width
        img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    
    # Step 2: Increase contrast
    print(f"[3/4] Enhancing contrast...")
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l = clahe.apply(l)
    enhanced = cv2.merge([l, a, b])
    enhanced = cv2.cvtColor(enhanced, cv2.COLOR_LAB2BGR)
    
    # Step 3: Sharpen
    print(f"[4/4] Sharpening...")
    kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
    sharpened = cv2.filter2D(enhanced, -1, kernel)
    
    # Generate output path
    if output_path is None:
        base, ext = os.path.splitext(image_path)
        output_path = f"{base}_enhanced.png"
    
    cv2.imwrite(output_path, sharpened)
    
    new_size = os.path.getsize(output_path) / 1024 / 1024
    print(f"\n[OK] Saved: {output_path}")
    print(f"     Size: {original_size:.1f}MB -> {new_size:.1f}MB")
    
    return output_path


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python image_preprocessor.py <image_path> [method]")
        print("Methods: bw (default), color")
        sys.exit(1)
    
    image_path = sys.argv[1]
    method = sys.argv[2] if len(sys.argv) > 2 else "bw"
    
    if method == "color":
        preprocess_keep_color(image_path)
    else:
        preprocess_for_ocr(image_path)
