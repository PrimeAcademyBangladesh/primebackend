"""Model package exports.

Provides convenient imports for commonly used models.
"""

from .models_auth import CustomUser, Profile, Skill
from .models_cart import Cart, CartItem, Wishlist
from .models_custom_payment import CustomPayment, EventRegistration
from .models_footer import Footer, LinkGroup, QuickLink, SocialLink
from .models_progress import (
    CourseProgress,
    StudentModuleProgress,
    # OLD models removed: ModuleAssignment, ModuleQuiz, StudentAssignmentSubmission, StudentQuizAttempt
    # Use NEW system: Quiz, Assignment, LiveClass from models_module.py
)
