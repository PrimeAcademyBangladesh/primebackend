"""Tests for Skill ViewSet permissions."""

from django.test import TestCase

from rest_framework import status
from rest_framework.test import APIClient

from api.models.models_auth import CustomUser, Skill


class SkillPermissionTestCase(TestCase):
    """Test skill permissions for different user roles."""

    def setUp(self):
        """Set up test users and skills."""
        self.client = APIClient()

        # Create test users with unique phone numbers
        self.student = CustomUser.objects.create_user(
            email="student@test.com", password="testpass123", phone="+1234567890", role="student", is_enabled=True
        )

        self.staff = CustomUser.objects.create_user(
            email="staff@test.com", password="testpass123", phone="+1234567891", role="staff", is_enabled=True
        )

        self.admin = CustomUser.objects.create_user(
            email="admin@test.com", password="testpass123", phone="+1234567892", role="admin", is_enabled=True
        )

        # Create test skill
        self.skill = Skill.objects.create(name="Python", is_active=True)

    def test_student_can_list_skills(self):
        """Students should be able to list all skills."""
        self.client.force_authenticate(user=self.student)
        response = self.client.get("/api/skills/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("data", response.data)

    def test_student_can_retrieve_skill(self):
        """Students should be able to view individual skills."""
        self.client.force_authenticate(user=self.student)
        response = self.client.get(f"/api/skills/{self.skill.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["name"], "Python")

    def test_student_can_create_skill(self):
        """Students should be able to create new skills."""
        self.client.force_authenticate(user=self.student)

        data = {"name": "JavaScript", "is_active": True}

        response = self.client.post("/api/skills/", data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Skill.objects.filter(name="JavaScript").exists())

    def test_student_cannot_update_skill(self):
        """Students should NOT be able to update existing skills."""
        self.client.force_authenticate(user=self.student)

        data = {"name": "Python 3.11", "is_active": True}

        response = self.client.put(f"/api/skills/{self.skill.id}/", data)

        # Should be forbidden (403) for students
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Verify skill was not updated
        self.skill.refresh_from_db()
        self.assertEqual(self.skill.name, "Python")

    def test_student_cannot_partial_update_skill(self):
        """Students should NOT be able to partially update skills."""
        self.client.force_authenticate(user=self.student)

        data = {"name": "Python Advanced"}

        response = self.client.patch(f"/api/skills/{self.skill.id}/", data)

        # Should be forbidden (403) for students
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Verify skill was not updated
        self.skill.refresh_from_db()
        self.assertEqual(self.skill.name, "Python")

    def test_student_cannot_delete_skill(self):
        """Students should NOT be able to delete skills."""
        self.client.force_authenticate(user=self.student)

        response = self.client.delete(f"/api/skills/{self.skill.id}/")

        # Should be forbidden (403) for students
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Verify skill still exists
        self.assertTrue(Skill.objects.filter(id=self.skill.id).exists())

    def test_staff_can_update_skill(self):
        """Staff should be able to update skills."""
        self.client.force_authenticate(user=self.staff)

        data = {"name": "Python 3.11", "is_active": True}

        response = self.client.put(f"/api/skills/{self.skill.id}/", data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify skill was updated
        self.skill.refresh_from_db()
        self.assertEqual(self.skill.name, "Python 3.11")

    def test_staff_can_partial_update_skill(self):
        """Staff should be able to partially update skills."""
        self.client.force_authenticate(user=self.staff)

        data = {"is_active": False}

        response = self.client.patch(f"/api/skills/{self.skill.id}/", data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify skill was updated
        self.skill.refresh_from_db()
        self.assertFalse(self.skill.is_active)

    def test_staff_can_delete_skill(self):
        """Staff should be able to delete skills."""
        self.client.force_authenticate(user=self.staff)

        # Create a skill to delete
        skill_to_delete = Skill.objects.create(name="ToDelete")

        response = self.client.delete(f"/api/skills/{skill_to_delete.id}/")

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Verify skill was deleted
        self.assertFalse(Skill.objects.filter(id=skill_to_delete.id).exists())

    def test_admin_can_update_skill(self):
        """Admin should be able to update skills."""
        self.client.force_authenticate(user=self.admin)

        data = {"name": "Python Expert", "is_active": True}

        response = self.client.put(f"/api/skills/{self.skill.id}/", data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify skill was updated
        self.skill.refresh_from_db()
        self.assertEqual(self.skill.name, "Python Expert")

    def test_unauthenticated_cannot_access_skills(self):
        """Unauthenticated users should not be able to access skills."""
        # No authentication

        response = self.client.get("/api/skills/")

        # Should require authentication
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_student_can_create_duplicate_skill_fails(self):
        """Creating a skill with duplicate name should fail (unique constraint)."""
        self.client.force_authenticate(user=self.student)

        data = {"name": "Python", "is_active": True}  # Already exists

        response = self.client.post("/api/skills/", data)

        # Should fail due to unique constraint
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_skill_name_is_case_sensitive(self):
        """Skill names should maintain case sensitivity."""
        self.client.force_authenticate(user=self.student)

        data = {"name": "python", "is_active": True}  # lowercase

        response = self.client.post("/api/skills/", data)

        # Should succeed (different from 'Python')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Skill.objects.filter(name="python").exists())

        # Both should exist
        self.assertEqual(Skill.objects.filter(name__iexact="python").count(), 2)
