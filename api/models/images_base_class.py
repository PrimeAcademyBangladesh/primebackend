from django.core.exceptions import ValidationError
from django.db import models

from api.utils.image_utils import optimize_image


class OptimizedImageModel(models.Model):
    """
    Abstract base class for models with ImageField(s) that need:
    - Automatic optimization (resize + compression)
    - Old file deletion on update
    - Built-in validation
    - Works for admin & API
    """

    class Meta:
        abstract = True

    # Per-model dict of fields to optimize:
    # {'field_name': {'max_size': (w,h), 'min_size': (w,h), 'max_bytes': bytes, 'min_bytes': bytes, 'max_upload_mb': 10}}
    IMAGE_FIELDS_OPTIMIZATION = {}

    def clean(self):
        """
        Validate image fields before saving with detailed error messages
        """
        super().clean()

        allowed_types = ["image/jpeg", "image/jpg", "image/png", "image/gi", "image/webp"]

        for field_name, options in self.IMAGE_FIELDS_OPTIMIZATION.items():
            image_field = getattr(self, field_name)

            if image_field and hasattr(image_field, "file"):
                # Check file size (default 10MB limit before optimization)
                max_upload_mb = options.get("max_upload_mb", 10)
                max_upload_bytes = max_upload_mb * 1024 * 1024

                if image_field.size > max_upload_bytes:
                    # Get human-readable field name
                    field_verbose_name = getattr(
                        self._meta.get_field(field_name), "verbose_name", field_name.replace("_", " ").title()
                    )

                    # Calculate current file size in MB
                    current_size_mb = round(image_field.size / (1024 * 1024), 2)

                    # Create helpful suggestions based on the file size
                    if current_size_mb > max_upload_mb * 2:
                        suggestion = "Try using an online image compressor like TinyPNG or CompressJPEG."
                    elif current_size_mb > max_upload_mb * 1.5:
                        suggestion = "Please reduce image quality or resize to smaller dimensions."
                    else:
                        suggestion = "Try compressing the image slightly or converting to JPEG format."

                    raise ValidationError(
                        {
                            field_name: (
                                f"📸 {field_verbose_name} is too large to upload! "
                                f"Your image: {current_size_mb}MB | Maximum allowed: {max_upload_mb}MB. "
                                f"💡 {suggestion}"
                            )
                        }
                    )

                # Check file type (if content_type is available)
                if hasattr(image_field, "content_type"):
                    if image_field.content_type not in allowed_types:
                        field_verbose_name = getattr(
                            self._meta.get_field(field_name), "verbose_name", field_name.replace("_", " ").title()
                        )

                        # Get just the file extension for cleaner message
                        file_type = image_field.content_type.split("/")[-1].upper() if image_field.content_type else "Unknown"

                        raise ValidationError(
                            {
                                field_name: (
                                    f"🚫 {field_verbose_name} format not supported! "
                                    f"Your file: {file_type} | Supported formats: JPEG, PNG, GIF, WebP. "
                                    "💡 Please convert your image to one of the supported formats."
                                )
                            }
                        )

    def save(self, *args, **kwargs):
        # Run validation unless skip_validation is True
        if not kwargs.pop("skip_validation", False):
            self.full_clean()

        # Get the force_insert flag to determine if this is a new instance
        is_new = self.pk is None or kwargs.get("force_insert", False)

        # 1️⃣ Delete old files if changed (only for updates)
        if not is_new:
            try:
                old_instance = self.__class__.objects.get(pk=self.pk)
                for field_name in self.IMAGE_FIELDS_OPTIMIZATION.keys():
                    old_file = getattr(old_instance, field_name)
                    new_file = getattr(self, field_name)

                    # Check if the file has changed
                    old_name = getattr(old_file, "name", None) if old_file else None
                    new_name = getattr(new_file, "name", None) if new_file else None

                    if old_name and new_name and old_name != new_name:
                        # Delete the old file from storage
                        old_file.delete(save=False)
            except self.__class__.DoesNotExist:
                pass

        # 2️⃣ Optimize new images BEFORE saving
        for field_name, options in self.IMAGE_FIELDS_OPTIMIZATION.items():
            image_field = getattr(self, field_name)

            # Check if there's a new image to optimize
            if image_field and hasattr(image_field, "file"):
                try:
                    # Detect if file changed by checking multiple conditions
                    file_changed = False

                    # Check 1: _committed attribute (for new uploads)
                    if hasattr(image_field, "_committed") and not image_field._committed:
                        file_changed = True

                    # Check 2: Compare with old instance (for updates)
                    if not is_new and not file_changed:
                        try:
                            old_instance = self.__class__.objects.get(pk=self.pk)
                            old_file = getattr(old_instance, field_name)
                            old_name = getattr(old_file, "name", None) if old_file else None
                            new_name = getattr(image_field, "name", None)

                            if old_name != new_name:
                                file_changed = True
                        except self.__class__.DoesNotExist:
                            file_changed = True

                    # Check 3: For brand new instances
                    if is_new:
                        file_changed = True

                    # Only optimize if file has changed
                    if file_changed:
                        optimize_image(
                            image_field,
                            max_size=options.get("max_size", (800, 800)),
                            min_size=options.get("min_size", None),
                            max_bytes=options.get("max_bytes", 200 * 1024),
                            min_bytes=options.get("min_bytes", None),
                        )
                except Exception as e:
                    print(f"Failed to optimize {field_name}: {e}")
                    import traceback

                    traceback.print_exc()

        # 3️⃣ Save the instance
        super().save(*args, **kwargs)
