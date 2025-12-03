"""
Tests for image upload error handling to ensure proper error messages
are returned to the frontend instead of network errors.
"""
from io import BytesIO
from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient
from PIL import Image

from api.models.models_auth import CustomUser
from api.models.models_employee import Employee, Department


class ImageUploadErrorTests(TestCase):
    """Test image upload validation and error responses"""

    def setUp(self):
        self.client = APIClient()
        
        # Create admin user for testing (employees require admin permission)
        self.admin_user = CustomUser.objects.create_user(
            email='admin@test.com',
            password='testpass123',
            role='admin',
            first_name='Admin',
            last_name='User',
            phone='+1234567890'
        )
        self.client.force_authenticate(user=self.admin_user)
        
        # Create a department for employee
        self.department = Department.objects.create(
            name='Test Department',
            is_active=True
        )

    def create_test_image(self, size_kb, format='JPEG', dimensions=(1000, 1000)):
        """
        Create a test image of approximately the specified size.
        
        :param size_kb: Approximate size in kilobytes
        :param format: Image format (JPEG, PNG)
        :param dimensions: Image dimensions (width, height)
        :return: SimpleUploadedFile
        """
        # Create an image with the specified dimensions
        img = Image.new('RGB', dimensions, color='red')
        
        # Save to BytesIO with appropriate quality to reach target size
        img_io = BytesIO()
        
        if format == 'JPEG':
            # For JPEG, use quality to control size
            quality = 95
            img.save(img_io, format='JPEG', quality=quality)
            
            # Adjust quality if needed to reach target size
            while img_io.tell() < size_kb * 1024 and quality < 100:
                img_io = BytesIO()
                quality = min(100, quality + 5)
                img.save(img_io, format='JPEG', quality=quality)
            
            # If still too small, increase dimensions
            while img_io.tell() < size_kb * 1024 and dimensions[0] < 10000:
                dimensions = (dimensions[0] + 500, dimensions[1] + 500)
                img = Image.new('RGB', dimensions, color='red')
                img_io = BytesIO()
                img.save(img_io, format='JPEG', quality=100)
        else:
            img.save(img_io, format=format)
        
        img_io.seek(0)
        
        # Pad with extra data if needed to reach target size
        current_size = len(img_io.getvalue())
        if current_size < size_kb * 1024:
            padding = b'\x00' * (size_kb * 1024 - current_size)
            content = img_io.getvalue() + padding
        else:
            content = img_io.getvalue()
        
        actual_size_mb = len(content) / (1024 * 1024)
        print(f"\n📦 Created test image: {actual_size_mb:.2f}MB ({format})")
        
        return SimpleUploadedFile(
            f"test_image.{format.lower()}",
            content,
            content_type=f'image/{format.lower()}'
        )

    def test_upload_oversized_image_returns_proper_error(self):
        """
        Test that uploading an image larger than the limit returns
        a proper error response (not a network error).
        """
        print("\n" + "="*60)
        print("TEST: Upload Oversized Image (15MB)")
        print("="*60)
        
        # Create a 15MB image (exceeds 10MB limit)
        large_image = self.create_test_image(
            size_kb=15 * 1024,  # 15MB
            format='JPEG',
            dimensions=(3000, 3000)
        )
        
        # Try to create an employee with the large image
        data = {
            'employee_id': 'EMP001',
            'employee_name': 'Test Employee',
            'job_title': 'Developer',
            'department_id': str(self.department.id),
            'employee_image': large_image,
            'is_active': True
        }
        
        response = self.client.post('/api/employees/', data, format='multipart')
        
        print(f"\n📡 Response Status: {response.status_code}")
        print(f"📄 Response Data: {response.data}")
        
        # Should return 400 Bad Request (not 500 or network error)
        self.assertEqual(response.status_code, 400)
        
        # Should have a clear error message
        self.assertFalse(response.data.get('success', True))
        
        # Check that error mentions file size
        error_message = str(response.data)
        self.assertTrue(
            any(keyword in error_message.lower() for keyword in ['size', 'large', 'mb', 'maximum']),
            f"Error message should mention file size. Got: {error_message}"
        )
        
        print(f"✅ Proper error returned: {response.data}")

    def test_upload_wrong_format_returns_proper_error(self):
        """
        Test that uploading an unsupported image format returns
        a proper error response.
        """
        print("\n" + "="*60)
        print("TEST: Upload Wrong Format (SVG)")
        print("="*60)
        
        # Create a fake SVG file
        svg_content = b'<svg xmlns="http://www.w3.org/2000/svg"><circle r="50"/></svg>'
        svg_file = SimpleUploadedFile(
            "test_image.svg",
            svg_content,
            content_type='image/svg+xml'
        )
        
        data = {
            'employee_id': 'EMP002',
            'employee_name': 'Test Employee 2',
            'job_title': 'Designer',
            'department_id': str(self.department.id),
            'employee_image': svg_file,
            'is_active': True
        }
        
        response = self.client.post('/api/employees/', data, format='multipart')
        
        print(f"\n📡 Response Status: {response.status_code}")
        print(f"📄 Response Data: {response.data}")
        
        # Should return 400 Bad Request
        self.assertEqual(response.status_code, 400)
        
        # Should have error about format or invalid image
        error_message = str(response.data)
        self.assertTrue(
            any(keyword in error_message.lower() for keyword in ['format', 'supported', 'jpeg', 'png', 'invalid', 'corrupted']),
            f"Error message should mention format or invalid image. Got: {error_message}"
        )
        
        print(f"✅ Proper error returned: {response.data}")

    def test_upload_valid_image_succeeds(self):
        """
        Test that uploading a valid image within limits succeeds.
        """
        print("\n" + "="*60)
        print("TEST: Upload Valid Image (100KB)")
        print("="*60)
        
        # Create a small valid image (100KB)
        valid_image = self.create_test_image(
            size_kb=100,  # 100KB - well within 10MB limit
            format='JPEG',
            dimensions=(400, 400)
        )
        
        data = {
            'employee_id': 'EMP003',
            'employee_name': 'Test Employee 3',
            'job_title': 'Manager',
            'department_id': str(self.department.id),
            'employee_image': valid_image,
            'is_active': True
        }
        
        response = self.client.post('/api/employees/', data, format='multipart')
        
        print(f"\n📡 Response Status: {response.status_code}")
        print(f"📄 Response Data: {response.data}")
        
        # Should succeed
        self.assertIn(response.status_code, [200, 201])
        self.assertTrue(response.data.get('success', False))
        
        print(f"✅ Upload successful!")

    def test_django_request_size_limit(self):
        """
        Test Django's DATA_UPLOAD_MAX_MEMORY_SIZE setting.
        This will cause a SuspiciousOperation error if exceeded.
        """
        print("\n" + "="*60)
        print("TEST: Django Request Size Limit (11MB)")
        print("="*60)
        
        # Create an 11MB image (exceeds Django's 10MB DATA_UPLOAD_MAX_MEMORY_SIZE)
        huge_image = self.create_test_image(
            size_kb=11 * 1024,  # 11MB
            format='JPEG',
            dimensions=(4000, 4000)
        )
        
        data = {
            'employee_id': 'EMP004',
            'employee_name': 'Test Employee 4',
            'job_title': 'Director',
            'department_id': str(self.department.id),
            'employee_image': huge_image,
            'is_active': True
        }
        
        response = self.client.post('/api/employees/', data, format='multipart')
        
        print(f"\n📡 Response Status: {response.status_code}")
        print(f"📄 Response Data: {response.data if hasattr(response, 'data') else response.content}")
        
        # Django should return 413 (Request Entity Too Large) or 400
        self.assertIn(response.status_code, [400, 413])
        
        print(f"✅ Request rejected by Django")


class FrontendErrorHandlingGuide(TestCase):
    """
    Documentation test case that explains how to handle these errors in React.
    This test always passes and serves as living documentation.
    """

    def test_frontend_error_handling_guide(self):
        """
        📚 FRONTEND ERROR HANDLING GUIDE FOR REACT
        
        When uploading images, you may encounter these scenarios:
        
        1️⃣ FILE TOO LARGE (Before Upload):
           - Check file size in JavaScript before uploading
           - Example:
             ```javascript
             if (file.size > 10 * 1024 * 1024) {
               toast.error(`File too large! Maximum: 10MB, Your file: ${(file.size/1024/1024).toFixed(2)}MB`);
               return;
             }
             ```
        
        2️⃣ VALIDATION ERROR (400 Response):
           - Backend returns structured error with field names
           - Example response:
             {
               "success": false,
               "error": "Validation failed",
               "errors": {
                 "image": ["📸 Image is too large to upload! Your image: 15MB | Maximum allowed: 10MB. 💡 Try using an online image compressor."]
               }
             }
           
           - React handling:
             ```javascript
             try {
               const response = await axios.post('/api/employees/', formData);
               // Success
             } catch (error) {
               if (error.response?.status === 400) {
                 const errors = error.response.data.errors || {};
                 
                 // Show specific field errors
                 Object.entries(errors).forEach(([field, messages]) => {
                   messages.forEach(msg => toast.error(msg));
                 });
               } else if (error.response?.status === 413) {
                 toast.error('File too large! Maximum: 10MB. Please reduce file size.');
               } else {
                 toast.error('Upload failed. Please try again.');
               }
             }
             ```
        
        3️⃣ NETWORK ERROR (No Response):
           - Timeout or connection issues
           - Example:
             ```javascript
             catch (error) {
               if (!error.response) {
                 // Network error
                 toast.error('Network error. Please check your connection.');
               }
             }
             ```
        
        4️⃣ COMPLETE EXAMPLE:
           ```javascript
           const uploadImage = async (file) => {
             // 1. Validate file size
             const MAX_SIZE = 10 * 1024 * 1024; // 10MB
             if (file.size > MAX_SIZE) {
               toast.error(
                 `Image too large: ${(file.size/1024/1024).toFixed(2)}MB. ` +
                 `Maximum: 10MB. Please compress the image.`
               );
               return;
             }
             
             // 2. Validate file type
             const ALLOWED_TYPES = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp'];
             if (!ALLOWED_TYPES.includes(file.type)) {
               toast.error('Unsupported format. Please use JPEG, PNG, or WebP.');
               return;
             }
             
             // 3. Show loading state
             setUploading(true);
             
             // 4. Upload with proper error handling
             const formData = new FormData();
             formData.append('image', file);
             formData.append('name', name);
             // ... other fields
             
             try {
               const response = await axios.post('/api/employees/', formData, {
                 headers: { 'Content-Type': 'multipart/form-data' },
                 timeout: 30000, // 30 second timeout
                 onUploadProgress: (progressEvent) => {
                   const percentCompleted = Math.round(
                     (progressEvent.loaded * 100) / progressEvent.total
                   );
                   setUploadProgress(percentCompleted);
                 },
               });
               
               toast.success('Upload successful!');
               return response.data;
               
             } catch (error) {
               // Handle different error types
               if (error.response) {
                 // Server responded with error status
                 const { status, data } = error.response;
                 
                 if (status === 400) {
                   // Validation error
                   const errors = data.errors || {};
                   const errorMessages = Object.values(errors).flat();
                   errorMessages.forEach(msg => toast.error(msg));
                 } else if (status === 413) {
                   toast.error('File too large for server. Maximum: 10MB.');
                 } else if (status === 401) {
                   toast.error('Please login to upload images.');
                 } else {
                   toast.error(data.error || 'Upload failed. Please try again.');
                 }
               } else if (error.request) {
                 // Request made but no response (network error)
                 toast.error('Network error. Please check your connection and try again.');
               } else {
                 // Error setting up request
                 toast.error('Upload failed. Please try again.');
               }
               
               throw error;
             } finally {
               setUploading(false);
               setUploadProgress(0);
             }
           };
           ```
        
        5️⃣ USER-FRIENDLY MESSAGES:
           - ✅ "Image too large: 15MB. Maximum: 10MB. Please compress the image."
           - ✅ "Unsupported format. Please use JPEG, PNG, GIF, or WebP."
           - ✅ "Network error. Please check your connection."
           - ❌ "Request failed with status code 400"
           - ❌ "Network Error"
        """
        # This test always passes - it's documentation
        self.assertTrue(True, "Frontend error handling guide provided")
        
        print("\n" + "="*80)
        print("📚 FRONTEND ERROR HANDLING GUIDE")
        print("="*80)
        print(self.test_frontend_error_handling_guide.__doc__)
        print("="*80)
