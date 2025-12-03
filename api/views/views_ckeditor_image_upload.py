import os
import uuid
from datetime import datetime
from io import BytesIO

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from drf_spectacular.utils import extend_schema
from PIL import Image
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from api.permissions import IsStaff
from api.utils.admin_session_auth import CombinedAuthentication


@extend_schema(
    tags=["CKEditor Image Upload"],
    request={
        'multipart/form-data': {
            'type': 'object',
            'properties': {
                'upload': {'type': 'string', 'format': 'binary'}
            }
        }
    }
)
class CKEditorImageUploadView(APIView):
    authentication_classes = [CombinedAuthentication]
    permission_classes = [IsStaff]

    def post(self, request, *args, **kwargs):
        if 'upload' not in request.FILES:
            return Response(
                {'error': {'message': 'No file provided'}},
                status=status.HTTP_400_BAD_REQUEST
            )

        uploaded_file = request.FILES['upload']

        try:
            # Validate file type
            allowed_types = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/webp']
            if uploaded_file.content_type not in allowed_types:
                file_type = uploaded_file.content_type.split('/')[-1].upper() if uploaded_file.content_type else 'Unknown'
                return Response(
                    {
                        'error': {
                            'message': (
                                f'🚫 Image format not supported! '
                                f'Your file: {file_type} | Supported formats: JPEG, PNG, GIF, WebP. '
                                f'💡 Please convert your image to one of the supported formats.'
                            )
                        }
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Validate file size (10MB max)
            max_size = 10 * 1024 * 1024
            if uploaded_file.size > max_size:
                current_size_mb = round(uploaded_file.size / (1024 * 1024), 2)
                
                # Create helpful suggestions
                if current_size_mb > 20:
                    suggestion = "Try using an online image compressor like TinyPNG or CompressJPEG."
                elif current_size_mb > 15:
                    suggestion = "Please reduce image quality or resize to smaller dimensions."
                else:
                    suggestion = "Try compressing the image slightly or converting to JPEG format."
                
                return Response(
                    {
                        'error': {
                            'message': (
                                f'📸 Image is too large to upload! '
                                f'Your image: {current_size_mb}MB | Maximum allowed: 10MB. '
                                f'💡 {suggestion}'
                            )
                        }
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Generate unique filename
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            unique_id = uuid.uuid4().hex[:8]
            filename = f"{timestamp}_{unique_id}.webp"

            # Organized upload directory
            today = datetime.now()
            upload_dir = f"uploads/{today.year}/{today.month:02d}"
            filepath = os.path.join(upload_dir, filename)

            # Process image
            image = Image.open(uploaded_file)
            if image.mode in ('RGBA', 'P'):
                image = image.convert('RGB')

            if image.width > 1920:
                ratio = 1920 / image.width
                new_height = int(image.height * ratio)
                image = image.resize((1920, new_height), Image.Resampling.LANCZOS)

            # Save as optimized WebP
            output = BytesIO()
            image.save(output, format='WEBP', quality=85, optimize=True)
            output.seek(0)

            # Save file using Django’s storage
            saved_path = default_storage.save(filepath, ContentFile(output.getvalue()))
            file_url = default_storage.url(saved_path)

            # Absolute URL
            site_base = getattr(settings, "SITE_BASE_URL", "http://127.0.0.1:8000")
            absolute_url = f"{site_base}{file_url}"

            print(f"✅ CKEditor upload successful: {absolute_url}")
            print(f"📁 Saved storage path: {saved_path}")

            return Response({'url': absolute_url}, status=status.HTTP_201_CREATED)

        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response(
                {'error': {'message': f'Failed to process image: {str(e)}'}},
                status=status.HTTP_400_BAD_REQUEST
            )
