"""Authentication, current user and admin-user management."""

from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView

from ..activity import get_client_ip, log_user_activity
from ..models import Department, LoginAttempt, Specialization
from ..permissions import IsAdminRole, IsSuperAdmin
from ..serializers import (
    AdminUserSerializer, AdminUserWriteSerializer, CurrentUserSerializer,
    LoginResponseSerializer, LoginSerializer, MessageSerializer,
)

User = get_user_model()


class LoginView(TokenObtainPairView):
    """Obtain a JWT pair. Also returns the user profile and records the attempt."""
    serializer_class = LoginSerializer
    permission_classes = [AllowAny]

    @extend_schema(responses=LoginResponseSerializer)
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        LoginAttempt.objects.create(
            username=str(request.data.get('username', ''))[:150],
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            success=response.status_code == 200,
            failure_reason='' if response.status_code == 200 else 'invalid_credentials',
        )
        return response

    def handle_exception(self, exc):
        # Failed logins raise before post() returns; record them too.
        response = super().handle_exception(exc)
        if self.request.method == 'POST' and response.status_code == 401:
            LoginAttempt.objects.create(
                username=str(self.request.data.get('username', ''))[:150],
                ip_address=get_client_ip(self.request),
                user_agent=self.request.META.get('HTTP_USER_AGENT', ''),
                success=False,
                failure_reason='invalid_credentials',
            )
        return response


@extend_schema(responses=CurrentUserSerializer)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_current_user(request):
    return Response(CurrentUserSerializer(request.user).data)


# --------------------------
# Admin users
# --------------------------
def _apply_user_fields(user, data):
    if data.get('name') and not (data.get('first_name') or data.get('last_name')):
        first, _, last = data['name'].partition(' ')
        user.first_name, user.last_name = first, last
    for field in ('first_name', 'last_name', 'phone', 'job_title', 'role'):
        if field in data:
            setattr(user, field, data[field])
    if 'email' in data:
        if not user.username or user.username == user.email:
            user.username = data['email']
        user.email = data['email']
    if data.get('username'):
        user.username = data['username']
    if 'employee_id' in data:
        user.employee_id = data['employee_id'] or None
    if 'department_id' in data:
        user.department = Department.objects.filter(id=data['department_id']).first() \
            if data['department_id'] else None
    if 'specialization_id' in data:
        user.specialization = Specialization.objects.filter(id=data['specialization_id']).first() \
            if data['specialization_id'] else None
    if data.get('password'):
        user.set_password(data['password'])


@extend_schema(responses=AdminUserSerializer(many=True))
@api_view(['GET'])
@permission_classes([IsAdminRole])
def get_admin_users(request):
    users = User.objects.filter(is_active=True).select_related('department', 'specialization') \
        .order_by('first_name', 'last_name')
    return Response(AdminUserSerializer(users, many=True).data)


@extend_schema(request=AdminUserWriteSerializer, responses={201: AdminUserSerializer})
@api_view(['POST'])
@permission_classes([IsSuperAdmin])
def create_admin_user(request):
    serializer = AdminUserWriteSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    username = data.get('username') or data.get('email')
    if not username:
        return Response({'error': 'username or email is required'}, status=status.HTTP_400_BAD_REQUEST)
    if User.objects.filter(username=username).exists():
        return Response({'error': 'A user with this username already exists'}, status=status.HTTP_400_BAD_REQUEST)
    if not data.get('password'):
        return Response({'error': 'password is required (min 8 characters)'}, status=status.HTTP_400_BAD_REQUEST)

    user = User(username=username, role=data.get('role', 'staff'))
    _apply_user_fields(user, data)
    user.save()
    log_user_activity(request.user, 'CREATE_ADMIN_USER', 'admin_users',
                      f'Created admin user: {user.full_name}', request, resource_id=user.id)
    return Response(AdminUserSerializer(user).data, status=status.HTTP_201_CREATED)


@extend_schema(methods=['PUT', 'PATCH'], request=AdminUserWriteSerializer, responses=AdminUserSerializer)
@extend_schema(methods=['DELETE'], request=None, responses=MessageSerializer)
@api_view(['PUT', 'PATCH', 'DELETE'])
@permission_classes([IsSuperAdmin])
def update_admin_user(request, user_id):
    user = User.objects.filter(id=user_id).first()
    if not user:
        return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'DELETE':
        return _deactivate(request, user)

    serializer = AdminUserWriteSerializer(data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    _apply_user_fields(user, serializer.validated_data)
    user.save()
    log_user_activity(request.user, 'UPDATE_ADMIN_USER', 'admin_users',
                      f'Updated admin user: {user.full_name}', request, resource_id=user.id)
    return Response(AdminUserSerializer(user).data)


@extend_schema(request=None, responses=MessageSerializer)
@api_view(['DELETE', 'POST'])
@permission_classes([IsSuperAdmin])
def delete_admin_user(request, user_id):
    user = User.objects.filter(id=user_id).first()
    if not user:
        return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
    return _deactivate(request, user)


def _deactivate(request, user):
    if user.pk == request.user.pk:
        return Response({'error': 'You cannot deactivate your own account'}, status=status.HTTP_400_BAD_REQUEST)
    # Soft delete keeps attendance sessions and audit history intact.
    user.is_active = False
    user.save(update_fields=['is_active'])
    log_user_activity(request.user, 'DELETE_ADMIN_USER', 'admin_users',
                      f'Deactivated admin user: {user.full_name}', request, resource_id=user.id)
    return Response({'message': 'User deactivated successfully'})
