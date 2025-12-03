import os
from io import BytesIO

from django.core.files.base import ContentFile

from PIL import Image
import pillow_heif
pillow_heif.register_heif_opener()


def get_compression_settings(original_size_bytes):
    """
    Get optimal compression settings based on original file size.
    Larger files get more aggressive compression to preserve quality while reducing size.
    
    :param original_size_bytes: Original file size in bytes
    :return: dict with initial_quality, min_quality, and quality_step
    """
    size_mb = original_size_bytes / (1024 * 1024)
    
    if size_mb >= 5:  # 5MB+ files: Aggressive compression
        return {
            'initial_quality': 75,
            'min_quality': 50,
            'quality_step': 5,
            'target_reduction': 0.8,  # Target 80% reduction
        }
    elif size_mb >= 3:  # 3-5MB files: Strong compression
        return {
            'initial_quality': 80,
            'min_quality': 60,
            'quality_step': 4,
            'target_reduction': 0.7,  # Target 70% reduction
        }
    elif size_mb >= 1:  # 1-3MB files: Moderate compression
        return {
            'initial_quality': 85,
            'min_quality': 70,
            'quality_step': 3,
            'target_reduction': 0.5,  # Target 50% reduction
        }
    elif size_mb >= 0.5:  # 500KB-1MB files: Light compression
        return {
            'initial_quality': 90,
            'min_quality': 80,
            'quality_step': 2,
            'target_reduction': 0.3,  # Target 30% reduction
        }
    else:  # <500KB files: Minimal compression, preserve quality
        return {
            'initial_quality': 95,
            'min_quality': 90,
            'quality_step': 1,
            'target_reduction': 0.1,  # Target 10% reduction
        }


def optimize_image(
    image_field,
    max_size=(800, 800),
    min_size=None,
    max_bytes=200 * 1024,
    min_bytes=None,
):
    """
    Optimize and convert any uploaded image to WebP with intelligent compression.
    Compression level adapts to original file size - larger files get more compression,
    smaller files preserve quality.

    :param image_field: Django ImageFieldFile instance
    :param max_size: (width, height) tuple for maximum dimensions
    :param min_size: (width, height) tuple for minimum dimensions (optional)
    :param max_bytes: max allowed file size in bytes after compression
    :param min_bytes: skip aggressive compression if image already smaller (optional)
    """
    if not image_field or not hasattr(image_field, "file"):
        return

    # Log file name and content type for debugging (Safari issues)
    file_name = getattr(image_field, "name", None)
    file_type = getattr(image_field, "content_type", None)
    print(f"[Image Upload Debug] File name: {file_name}, Content type: {file_type}")

    try:
        # Rewind file
        if hasattr(image_field.file, "seek"):
            image_field.file.seek(0)

        # Determine file size
        original_size = getattr(image_field, "size", None) or getattr(
            image_field.file, "size", None
        )
        
        if not original_size:
            print("Cannot determine original file size, using default compression")
            original_size = 1024 * 1024  # Default to 1MB for compression settings

        # Get intelligent compression settings based on file size
        compression_settings = get_compression_settings(original_size)
        
        print(f"📊 Original file: {original_size/1024:.1f}KB")
        print(f"🎯 Compression strategy: {compression_settings['initial_quality']}% quality, "
              f"target {compression_settings['target_reduction']*100:.0f}% reduction")
        
        # Check if we should skip aggressive compression (but still convert to WebP)
        skip_aggressive = min_bytes and original_size and original_size <= min_bytes
        if skip_aggressive:
            print(f"📁 Small file ({original_size} bytes), using gentle compression.")

        # Open and validate image
        try:
            img = Image.open(image_field.file)
            # Verify image can be loaded (triggers decompression)
            img.verify()
            # Re-open after verify (verify closes the file)
            image_field.file.seek(0)
            img = Image.open(image_field.file)
        except Exception as e:
            # Invalid/truncated image - skip optimization silently
            print(f"Skipping optimization: invalid image ({e})")
            return
        
        if img.format == "GIF":
            # Keep original GIF without conversion
            return

        # Convert mode to preserve alpha (transparency)
        if img.mode not in ("RGBA", "LA"):
            img = img.convert("RGBA")

        # Enforce min size if specified
        if min_size and (img.width < min_size[0] or img.height < min_size[1]):
            print(f"Skipping optimization: too small ({img.width}x{img.height}).")
            return

        # Resize down if larger than max_size (adjust based on file size)
        if skip_aggressive:
            # For small files, allow larger dimensions but still set reasonable limits
            max_allowed_size = (max_size[0] * 2, max_size[1] * 2)
            if img.width > max_allowed_size[0] or img.height > max_allowed_size[1]:
                img.thumbnail(max_allowed_size, Image.Resampling.LANCZOS)
                print(f"🔄 Gentle resize for small file: {img.size}")
        else:
            # For larger files, resize more aggressively
            if img.width > max_size[0] or img.height > max_size[1]:
                img.thumbnail(max_size, Image.Resampling.LANCZOS)
                print(f"🔄 Standard resize: {img.size}")

        # Calculate target file size based on original size and target reduction
        target_size = int(original_size * (1 - compression_settings['target_reduction']))
        actual_max_bytes = min(max_bytes, target_size) if not skip_aggressive else max_bytes
        
        print(f"🎯 Target size: {target_size/1024:.1f}KB (max: {actual_max_bytes/1024:.1f}KB)")

        # Compress to WebP in memory with intelligent quality
        thumb_io = BytesIO()
        quality = compression_settings['initial_quality']
        img.save(thumb_io, format="WEBP", quality=quality, method=6)
        content = thumb_io.getvalue()

        print(f"📝 Initial WebP ({quality}% quality): {len(content)/1024:.1f}KB")

        # Gradually lower quality if needed, but respect minimum quality for file size
        min_quality = compression_settings['min_quality']
        quality_step = compression_settings['quality_step']
        
        while len(content) > actual_max_bytes and quality > min_quality:
            thumb_io = BytesIO()
            quality -= quality_step
            img.save(thumb_io, format="WEBP", quality=quality, method=6)
            content = thumb_io.getvalue()
            print(f"📝 Adjusted WebP ({quality}% quality): {len(content)/1024:.1f}KB")

        # Final size report
        final_size = len(content)
        reduction = (1 - final_size/original_size) * 100
        print(f"✅ Final compression: {reduction:.1f}% reduction (quality: {quality}%)")

        # Create final WebP file
        thumb_io.seek(0)
        base_name = os.path.splitext(os.path.basename(image_field.name or "image"))[0]
        new_name = f"{base_name}.webp"

        # Replace the file content
        image_field.save(new_name, ContentFile(content), save=False)

        print(f"🎉 Optimized {new_name}: {final_size/1024:.1f}KB at {quality}% quality")

    except Exception as e:
        print(f"Image optimization failed: {e}")
        import traceback

        traceback.print_exc()

