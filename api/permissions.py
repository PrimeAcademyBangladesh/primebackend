"""Custom DRF permission classes for role-based access control.

Defines simple permission classes like IsAdmin, IsTeacher, and IsStudent
used throughout API view authorization.
"""

from rest_framework import permissions


class IsSuperAdmin(permissions.BasePermission):
    """
    Only superadmin can access.
    """
    def has_permission(self, request, view):
        """ 
        Check if the user is authenticated and has a role of superadmin.
        """
        return request.user.is_authenticated and request.user.role == "superadmin"


class IsAdmin(permissions.BasePermission):
    """
    Only admin users can access.
    """
    def has_permission(self, request, view):
        """ 
        Check if the user is authenticated and has a role of admin or superadmin.
        """
        return request.user.is_authenticated and request.user.role in ["admin", "superadmin"]


class IsStaff(permissions.BasePermission):
    """
    Only staff users can access.
    """
    def has_permission(self, request, view):
        """ 
        Check if the user is authenticated and has a role of staff, admin or superadmin.
        """
        return request.user.is_authenticated and request.user.role in ["staff", "admin", "superadmin"]


class IsAccountant(permissions.BasePermission):
    """
    Only accountant users can access.
    """
    def has_permission(self, request, view):
        """ 
        Check if the user is authenticated and has a role of accountant, admin or superadmin.
        """
        return request.user.is_authenticated and request.user.role in ["accountant", "superadmin"]



class IsTeacher(permissions.BasePermission):
    """
    Only teachers can access.
    """
    def has_permission(self, request, view):
        """
        Check if the user is authenticated and has a role of teacher, admin or superadmin.
        """
        return request.user.is_authenticated and request.user.role in ["teacher", "admin", "superadmin"]


class IsStudent(permissions.BasePermission):
    """
    Only students can access.
    """
    def has_permission(self, request, view):
        """
        Check if the user is authenticated and has a role of student.
        """
        return request.user.is_authenticated and request.user.role == "student"


class IsTeacherOrAdmin(permissions.BasePermission):
    """
    Teachers and admins can access.
    """
    def has_permission(self, request, view):
        """
        Check if the user is authenticated and has a role of teacher, admin or superadmin.
        """
        return request.user.is_authenticated and request.user.role in ["teacher", "admin", "superadmin"]


class IsStudentOwner(permissions.BasePermission):
    """
    Students can only access their own resources.
    """
    def has_permission(self, request, view):
        """
        Check if the user is authenticated and has a role of student.
        """
        return request.user.is_authenticated and request.user.role == "student"
    
    def has_object_permission(self, request, view, obj):
        """
        Check if the object belongs to the student.
        """
        return obj.student == request.user


class IsCourseManager(permissions.BasePermission):
    """
    Teachers, staff, and admins can manage courses.
    Used specifically for course CRUD operations.
    """
    def has_permission(self, request, view):
        """
        Check if the user is authenticated and has a role that can manage courses.
        """
        return request.user.is_authenticated and request.user.role in ["teacher", "staff", "admin", "superadmin"]
