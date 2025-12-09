"""Cart and Wishlist API Views"""
from rest_framework import status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse, OpenApiExample
from drf_spectacular.types import OpenApiTypes

from api.models.models_cart import Cart, CartItem, Wishlist
from api.models.models_course import Course
from api.models.models_order import Enrollment
from api.serializers.serializers_cart import (
    CartSerializer, CartItemSerializer, AddToCartSerializer,
    WishlistSerializer, AddToWishlistSerializer, MoveToCartResponseSerializer
)


def get_or_create_cart(request):
    """Get or create cart for authenticated or guest user"""
    if request.user.is_authenticated:
        cart, created = Cart.objects.get_or_create(user=request.user)
        return cart
    else:
        # For guest users, use session
        session_key = request.session.session_key
        if not session_key:
            request.session.save()
            session_key = request.session.session_key
        
        cart, created = Cart.objects.get_or_create(session_key=session_key)
        return cart


@extend_schema(
    summary="Get Shopping Cart",
    description="Retrieve the current user's shopping cart. Works for both authenticated and guest users (session-based).",
    responses={
        200: OpenApiResponse(
            response=CartSerializer,
            description="Cart retrieved successfully",
            examples=[
                OpenApiExample(
                    "Empty Cart",
                    value={
                        "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                        "items": [],
                        "total": "0",
                        "item_count": 0,
                        "created_at": "2024-01-01T00:00:00Z",
                        "updated_at": "2024-01-01T00:00:00Z"
                    }
                ),
                OpenApiExample(
                    "Cart with Items",
                    value={
                        "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                        "items": [
                            {
                                "id": "8fa85f64-5717-4562-b3fc-2c963f66afa6",
                                "course": {
                                    "id": "9fa85f64-5717-4562-b3fc-2c963f66afa6",
                                    "title": "Python Programming",
                                    "slug": "python-programming",
                                    "short_description": "Learn Python from scratch",
                                    "header_image": "https://example.com/image.jpg",
                                    "price": "99.99",
                                    "discounted_price": "79.99",
                                    "has_discount": True
                                },
                                "subtotal": "79.99",
                                "created_at": "2024-01-01T00:00:00Z",
                                "updated_at": "2024-01-01T00:00:00Z"
                            }
                        ],
                        "total": "79.99",
                        "item_count": 1,
                        "created_at": "2024-01-01T00:00:00Z",
                        "updated_at": "2024-01-01T00:00:00Z"
                    }
                )
            ]
        )
    },
    tags=["Shopping Cart"]
)
@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def cart_detail(request):
    """Get current user's cart"""
    cart = get_or_create_cart(request)
    serializer = CartSerializer(cart, context={'request': request})
    return Response(serializer.data)


@extend_schema(
    summary="Add Course to Cart",
    description="Add a course to the shopping cart. Works for both authenticated and guest users.",
    request=AddToCartSerializer,
    responses={
        201: OpenApiResponse(
            description="Course added to cart successfully",
            examples=[
                OpenApiExample(
                    "Course Added",
                    value={
                        "message": "Python Programming added to cart",
                        "cart": {
                            "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                            "items": [
                                {
                                    "id": "8fa85f64-5717-4562-b3fc-2c963f66afa6",
                                    "course": {
                                        "id": "9fa85f64-5717-4562-b3fc-2c963f66afa6",
                                        "title": "Python Programming",
                                        "slug": "python-programming",
                                        "short_description": "Learn Python",
                                        "header_image": "https://example.com/image.jpg",
                                        "price": "99.99",
                                        "discounted_price": "99.99",
                                        "has_discount": False
                                    },
                                    "subtotal": "99.99",
                                    "created_at": "2024-01-01T00:00:00Z",
                                    "updated_at": "2024-01-01T00:00:00Z"
                                }
                            ],
                            "total": "99.99",
                            "item_count": 1,
                            "created_at": "2024-01-01T00:00:00Z",
                            "updated_at": "2024-01-01T00:00:00Z"
                        }
                    }
                )
            ]
        ),
        200: OpenApiResponse(
            description="Course already in cart",
            examples=[
                OpenApiExample(
                    "Already in Cart",
                    value={
                        "message": "Python Programming is already in your cart",
                        "cart": {
                            "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                            "items": [],
                            "total": "99.99",
                            "item_count": 1
                        }
                    }
                )
            ]
        ),
        400: OpenApiResponse(
            description="Invalid course ID or course not available",
            examples=[
                OpenApiExample(
                    "Validation Error",
                    value={"course_id": ["Course not found or is not available."]}
                )
            ]
        )
    },
    tags=["Shopping Cart"]
)
@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def add_to_cart(request):
    """Add a course to cart"""
    serializer = AddToCartSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    course_id = serializer.validated_data['course_id']
    batch_id = serializer.validated_data.get('batch_id')
    course = get_object_or_404(Course, id=course_id, is_active=True)
    
    batch = None
    if batch_id:
        from api.models.models_course import CourseBatch
        batch = get_object_or_404(CourseBatch, id=batch_id, is_active=True, course=course)
    
    # Prevent adding to cart if the authenticated user is already enrolled
    if request.user and request.user.is_authenticated and not request.user.is_staff:
        if batch:
            # Check batch-specific enrollment
            if Enrollment.objects.filter(user=request.user, batch=batch, is_active=True).exists():
                return Response({
                    'error': f"You are already enrolled in {course.title} - {batch.get_display_name()}",
                    'detail': 'Cannot add enrolled courses to cart',
                    'already_enrolled': True,
                }, status=status.HTTP_400_BAD_REQUEST)
        else:
            # Check if user is enrolled in ANY batch of this course
            if Enrollment.objects.filter(user=request.user, course=course, is_active=True).exists():
                return Response({
                    'error': f"You are already enrolled in {course.title}",
                    'detail': 'Cannot add enrolled courses to cart',
                    'already_enrolled': True,
                }, status=status.HTTP_400_BAD_REQUEST)
    
    cart = get_or_create_cart(request)
    
    # SINGLE COURSE RESTRICTION: Only allow one course in cart at a time
    existing_items = cart.items.all()
    if existing_items.exists():
        existing_item = existing_items.first()
        # Check if trying to add a different course
        if existing_item.course.id != course_id or (existing_item.batch and existing_item.batch.id != batch_id):
            return Response({
                'error': 'You can only purchase one course at a time',
                'detail': f'Please remove "{existing_item.course.title}" from cart first',
                'existing_course': {
                    'id': str(existing_item.course.id),
                    'title': existing_item.course.title,
                    'batch': existing_item.batch.get_display_name() if existing_item.batch else None
                }
            }, status=status.HTTP_400_BAD_REQUEST)
    
    # Check if this course+batch combination already in cart
    cart_item, created = CartItem.objects.get_or_create(
        cart=cart,
        course=course,
        batch=batch
    )
    
    if created:
        message = f"{course.title} added to cart"
    else:
        message = f"{course.title} is already in your cart"
    
    cart_serializer = CartSerializer(cart, context={'request': request})
    return Response({
        'message': message,
        'cart': cart_serializer.data
    }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


@extend_schema(
    summary="Remove Item from Cart",
    description="Remove a specific item from the shopping cart using the cart item ID.",
    parameters=[
        OpenApiParameter(
            name='item_id',
            type=OpenApiTypes.UUID,
            location=OpenApiParameter.PATH,
            description='UUID of the cart item to remove'
        )
    ],
    responses={
        200: OpenApiResponse(
            description="Item removed successfully",
            examples=[
                OpenApiExample(
                    "Item Removed",
                    value={
                        "message": "Python Programming removed from cart",
                        "cart": {
                            "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                            "items": [],
                            "total": "0",
                            "item_count": 0
                        }
                    }
                )
            ]
        ),
        404: OpenApiResponse(
            description="Cart item not found",
            examples=[
                OpenApiExample(
                    "Not Found",
                    value={"error": "Cart item not found"}
                )
            ]
        )
    },
    tags=["Shopping Cart"]
)
@api_view(['DELETE'])
@permission_classes([permissions.AllowAny])
def remove_from_cart(request, item_id):
    """Remove an item from cart"""
    cart = get_or_create_cart(request)
    
    try:
        cart_item = CartItem.objects.get(id=item_id, cart=cart)
        course_title = cart_item.course.title
        cart_item.delete()
        
        cart_serializer = CartSerializer(cart, context={'request': request})
        return Response({
            'message': f"{course_title} removed from cart",
            'cart': cart_serializer.data
        })
    except CartItem.DoesNotExist:
        return Response(
            {'error': 'Cart item not found'},
            status=status.HTTP_404_NOT_FOUND
        )


@extend_schema(
    summary="Clear Shopping Cart",
    description="Remove all items from the shopping cart.",
    request=None,
    responses={
        200: OpenApiResponse(
            response=CartSerializer,
            description="Cart cleared successfully",
            examples=[
                OpenApiExample(
                    "Cart Cleared",
                    value={
                        "message": "Cart cleared successfully",
                        "cart": {
                            "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                            "items": [],
                            "total": "0",
                            "item_count": 0,
                            "created_at": "2024-01-01T00:00:00Z",
                            "updated_at": "2024-01-01T00:00:00Z"
                        }
                    }
                )
            ]
        )
    },
    tags=["Shopping Cart"]
)
@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def clear_cart(request):
    """Clear all items from cart"""
    cart = get_or_create_cart(request)
    cart.clear()
    
    cart_serializer = CartSerializer(cart, context={'request': request})
    return Response({
        'message': 'Cart cleared successfully',
        'cart': cart_serializer.data
    })


@extend_schema(
    summary="Get Wishlist",
    description="Retrieve the current authenticated user's wishlist. Authentication required.",
    responses={
        200: OpenApiResponse(
            response=WishlistSerializer,
            description="Wishlist retrieved successfully",
            examples=[
                OpenApiExample(
                    "Empty Wishlist",
                    value={
                        "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                        "courses": [],
                        "course_count": 0,
                        "created_at": "2024-01-01T00:00:00Z",
                        "updated_at": "2024-01-01T00:00:00Z"
                    }
                ),
                OpenApiExample(
                    "Wishlist with Courses",
                    value={
                        "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                        "courses": [
                            {
                                "id": "9fa85f64-5717-4562-b3fc-2c963f66afa6",
                                "title": "Python Programming",
                                "slug": "python-programming",
                                "short_description": "Learn Python from scratch",
                                "header_image": "https://example.com/image.jpg",
                                "price": "99.99",
                                "discounted_price": "79.99",
                                "has_discount": True
                            }
                        ],
                        "course_count": 1,
                        "created_at": "2024-01-01T00:00:00Z",
                        "updated_at": "2024-01-01T00:00:00Z"
                    }
                )
            ]
        ),
        401: OpenApiResponse(description="Authentication required")
    },
    tags=["Wishlist"]
)
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def wishlist_detail(request):
    """Get current user's wishlist"""
    wishlist, created = Wishlist.objects.get_or_create(user=request.user)
    serializer = WishlistSerializer(wishlist, context={'request': request})
    return Response(serializer.data)


@extend_schema(
    summary="Add Course to Wishlist",
    description="Add a course to the user's wishlist. Authentication required.",
    request=AddToWishlistSerializer,
    responses={
        200: OpenApiResponse(
            description="Course added to wishlist or already exists",
            examples=[
                OpenApiExample(
                    "Course Added",
                    value={
                        "message": "Python Programming added to wishlist",
                        "wishlist": {
                            "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                            "courses": [
                                {
                                    "id": "9fa85f64-5717-4562-b3fc-2c963f66afa6",
                                    "title": "Python Programming",
                                    "slug": "python-programming",
                                    "short_description": "Learn Python",
                                    "header_image": "https://example.com/image.jpg",
                                    "price": "99.99",
                                    "discounted_price": "99.99",
                                    "has_discount": False
                                }
                            ],
                            "course_count": 1
                        }
                    }
                ),
                OpenApiExample(
                    "Already in Wishlist",
                    value={
                        "message": "Python Programming is already in your wishlist",
                        "wishlist": {
                            "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                            "courses": [],
                            "course_count": 1
                        }
                    }
                )
            ]
        ),
        400: OpenApiResponse(
            description="Invalid course ID",
            examples=[
                OpenApiExample(
                    "Validation Error",
                    value={"course_id": ["Course not found or is not available."]}
                )
            ]
        ),
        401: OpenApiResponse(description="Authentication required")
    },
    tags=["Wishlist"]
)
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def add_to_wishlist(request):
    """Add a course to wishlist"""
    serializer = AddToWishlistSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    course_id = serializer.validated_data['course_id']
    course = get_object_or_404(Course, id=course_id, is_active=True)
    
    # Allow adding to wishlist even if enrolled in some batch
    # (user might want to enroll in a different batch)
    wishlist, created = Wishlist.objects.get_or_create(user=request.user)

    if course in wishlist.courses.all():
        message = f"{course.title} is already in your wishlist"
    else:
        wishlist.courses.add(course)
        message = f"{course.title} added to wishlist"
    
    wishlist_serializer = WishlistSerializer(wishlist, context={'request': request})
    return Response({
        'message': message,
        'wishlist': wishlist_serializer.data
    })


@extend_schema(
    summary="Remove Course from Wishlist",
    description="Remove a specific course from the user's wishlist.",
    parameters=[
        OpenApiParameter(
            name='course_id',
            type=OpenApiTypes.UUID,
            location=OpenApiParameter.PATH,
            description='UUID of the course to remove from wishlist'
        )
    ],
    responses={
        200: OpenApiResponse(
            description="Course removed or was not in wishlist",
            examples=[
                OpenApiExample(
                    "Course Removed",
                    value={
                        "message": "Python Programming removed from wishlist",
                        "wishlist": {
                            "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                            "courses": [],
                            "course_count": 0
                        }
                    }
                ),
                OpenApiExample(
                    "Not in Wishlist",
                    value={
                        "message": "Python Programming was not in your wishlist",
                        "wishlist": {
                            "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                            "courses": [],
                            "course_count": 0
                        }
                    }
                )
            ]
        ),
        401: OpenApiResponse(description="Authentication required"),
        404: OpenApiResponse(description="Course not found")
    },
    tags=["Wishlist"]
)
@api_view(['DELETE'])
@permission_classes([permissions.IsAuthenticated])
def remove_from_wishlist(request, course_id):
    """Remove a course from wishlist"""
    course = get_object_or_404(Course, id=course_id)
    wishlist, created = Wishlist.objects.get_or_create(user=request.user)
    
    if course in wishlist.courses.all():
        wishlist.courses.remove(course)
        message = f"{course.title} removed from wishlist"
    else:
        message = f"{course.title} was not in your wishlist"
    
    wishlist_serializer = WishlistSerializer(wishlist, context={'request': request})
    return Response({
        'message': message,
        'wishlist': wishlist_serializer.data
    })


@extend_schema(
    summary="Move Course from Wishlist to Cart",
    description="Remove a course from wishlist and add it to the shopping cart in one operation.",
    request=None,
    parameters=[
        OpenApiParameter(
            name='course_id',
            type=OpenApiTypes.UUID,
            location=OpenApiParameter.PATH,
            description='UUID of the course to move to cart'
        )
    ],
    responses={
        200: OpenApiResponse(
            response=MoveToCartResponseSerializer,
            description="Course moved to cart successfully",
            examples=[
                OpenApiExample(
                    "Course Moved",
                    value={
                        "message": "Python Programming moved to cart",
                        "cart": {
                            "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                            "items": [
                                {
                                    "id": "8fa85f64-5717-4562-b3fc-2c963f66afa6",
                                    "course": {
                                        "id": "9fa85f64-5717-4562-b3fc-2c963f66afa6",
                                        "title": "Python Programming",
                                        "slug": "python-programming",
                                        "short_description": "Learn Python",
                                        "header_image": "https://example.com/image.jpg",
                                        "price": "99.99",
                                        "discounted_price": "99.99",
                                        "has_discount": False
                                    },
                                    "subtotal": "99.99"
                                }
                            ],
                            "total": "99.99",
                            "item_count": 1
                        },
                        "wishlist": {
                            "id": "4fa85f64-5717-4562-b3fc-2c963f66afa6",
                            "courses": [],
                            "course_count": 0
                        }
                    }
                )
            ]
        ),
        401: OpenApiResponse(description="Authentication required"),
        404: OpenApiResponse(description="Course not found or not available")
    },
    tags=["Wishlist"]
)
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def move_to_cart(request, course_id):
    """Move a course from wishlist to cart"""
    course = get_object_or_404(Course, id=course_id, is_active=True)
    
    # Check if user is already enrolled in ANY batch of this course
    if not request.user.is_staff:
        if Enrollment.objects.filter(user=request.user, course=course, is_active=True).exists():
            return Response({
                'error': f"You are already enrolled in {course.title}",
                'detail': 'Cannot add enrolled courses to cart',
                'already_enrolled': True,
            }, status=status.HTTP_400_BAD_REQUEST)
    
    # Remove from wishlist
    wishlist, created = Wishlist.objects.get_or_create(user=request.user)
    if course in wishlist.courses.all():
        wishlist.courses.remove(course)
    
    # Add to cart (without batch, user will select batch at checkout)
    cart = get_or_create_cart(request)
    cart_item, created = CartItem.objects.get_or_create(
        cart=cart,
        course=course,
        batch=None  # User can select batch later
    )
    
    cart_serializer = CartSerializer(cart, context={'request': request})
    wishlist_serializer = WishlistSerializer(wishlist, context={'request': request})
    
    return Response({
        'message': f"{course.title} moved to cart",
        'cart': cart_serializer.data,
        'wishlist': wishlist_serializer.data
    })
