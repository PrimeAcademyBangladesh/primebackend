"""
Cart utility functions for merging guest carts with user carts.
"""
from api.models.models_cart import Cart, CartItem
from api.models.models_order import Enrollment


def merge_guest_cart_to_user(user, session_key):
    """
    Merge guest cart (session-based) with user's cart after login/registration.
    
    This function:
    1. Finds the guest cart by session_key
    2. Gets or creates the user's cart
    3. Transfers all items from guest cart to user cart (avoiding duplicates)
    4. Deletes the guest cart
    
    Args:
        user: Authenticated user object
        session_key: Session key from the request
        
    Returns:
        tuple: (user_cart, items_merged_count)
    """
    if not session_key:
        # No session key, just get or create user cart
        user_cart, _ = Cart.objects.get_or_create(user=user)
        return user_cart, 0
    
    try:
        # Find guest cart
        guest_cart = Cart.objects.get(session_key=session_key, user__isnull=True)
    except Cart.DoesNotExist:
        # No guest cart exists
        user_cart, _ = Cart.objects.get_or_create(user=user)
        return user_cart, 0
    
    # Get or create user cart
    user_cart, _ = Cart.objects.get_or_create(user=user)
    
    # Get all courses already in user's cart
    existing_course_ids = set(user_cart.items.values_list('course_id', flat=True))
    
    # Transfer items from guest cart to user cart
    items_merged = 0
    skipped_enrolled = 0
    for guest_item in guest_cart.items.all():
        # Skip if course is already in user's cart
        if guest_item.course_id in existing_course_ids:
            continue
        
        # Skip if user is enrolled in this course/batch
        if guest_item.batch:
            # Check batch-specific enrollment
            if Enrollment.objects.filter(user=user, batch=guest_item.batch, is_active=True).exists():
                skipped_enrolled += 1
                continue
        else:
            # Check if user is enrolled in ANY batch of this course
            if Enrollment.objects.filter(user=user, course=guest_item.course, is_active=True).exists():
                skipped_enrolled += 1
                continue
        
        # Add to user's cart
        CartItem.objects.create(
            cart=user_cart,
            course=guest_item.course,
            batch=guest_item.batch
        )
        items_merged += 1
    
    # Delete guest cart and its items
    guest_cart.delete()
    
    return user_cart, items_merged
