"""
Test script to demonstrate improved image upload error messages
"""

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile

import pytest

from api.models.models_auth import CustomUser, Profile


@pytest.mark.django_db
def test_image_error_messages():
    print("🧪 TESTING IMPROVED IMAGE UPLOAD ERROR MESSAGES")
    print("=" * 60)

    # Create a test user
    user = CustomUser.objects.create_user(
        email="errortest@example.com", password="pass123", first_name="Error", last_name="Test"
    )

    print("✅ Created test user")

    # Test 1: File too large (simulate 2.5MB profile image)
    print("\n📋 TEST 1: Large file upload (2.5MB > 1MB limit)")
    print("-" * 50)

    large_data = b"x" * (int(2.5 * 1024 * 1024))  # 2.5MB
    large_file = SimpleUploadedFile("large_profile.jpg", large_data, content_type="image/jpeg")

    try:
        profile = Profile(user=user, image=large_file)
        profile.full_clean()
        print("❌ UNEXPECTED: Validation should have failed")
    except ValidationError as e:
        print("✅ Validation Error Caught:")
        for field, messages in e.message_dict.items():
            if field == "image":
                print(f"   {field}: {messages[0]}")

    # Test 2: Unsupported file format
    print("\n📋 TEST 2: Unsupported file format (BMP)")
    print("-" * 50)

    bmp_data = b"fake_bmp_header" + b"x" * 1000
    bmp_file = SimpleUploadedFile("test_image.bmp", bmp_data, content_type="image/bmp")

    try:
        profile = Profile(user=user, image=bmp_file)
        profile.full_clean()
        print("❌ UNEXPECTED: Validation should have failed")
    except ValidationError as e:
        print("✅ Validation Error Caught:")
        for field, messages in e.message_dict.items():
            if field == "image":
                print(f"   {field}: {messages[0]}")

    # Test 3: Very large file (20MB) - different suggestion
    print("\n📋 TEST 3: Very large file upload (20MB)")
    print("-" * 50)

    huge_data = b"x" * (20 * 1024 * 1024)  # 20MB
    huge_file = SimpleUploadedFile("huge_profile.jpg", huge_data, content_type="image/jpeg")

    try:
        profile = Profile(user=user, image=huge_file)
        profile.full_clean()
        print("❌ UNEXPECTED: Validation should have failed")
    except ValidationError as e:
        print("✅ Validation Error Caught:")
        for field, messages in e.message_dict.items():
            if field == "image":
                print(f"   {field}: {messages[0]}")

    # Clean up
    user.delete()
    print("\n🧹 Cleaned up test data")
    print("\n🎉 ALL TESTS COMPLETED!")
    print("\nThese are the user-friendly error messages your frontend")
    print("developer will receive when users upload invalid images!")


if __name__ == "__main__":
    test_image_error_messages()
