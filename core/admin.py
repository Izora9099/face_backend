from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin

# Get the custom or default User model
User = get_user_model()

# Define a custom UserAdmin class
class CustomUserAdmin(UserAdmin):
    """
    Customizes the admin interface for the User model.
    """
    
    # list_display defines the fields to be shown in the user list view.
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff')
    
    # ordering specifies the default sorting order for the user list.
    # The '-' prefix indicates descending order.
    ordering = ('-date_joined',)
    
    # search_fields adds a search bar to the admin list view,
    # allowing searches across the specified fields.
    search_fields = ('username', 'email', 'first_name')
    
    # list_filter adds a sidebar for filtering users based on the
    # specified fields.
    list_filter = ('is_staff', 'is_superuser', 'groups')
    
    # fieldsets organize the user detail view into logical sections.
    # This improves readability and usability of the form.
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal Info', {'fields': ('first_name', 'last_name', 'email')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important Dates', {'fields': ('last_login', 'date_joined')}),
    )
    
    # readonly_fields makes the specified fields non-editable in the admin.
    # These fields are typically managed by Django automatically.
    readonly_fields = ('last_login', 'date_joined')

# Unregister the default User admin if it's already registered
# and then register our custom admin.
# This ensures that our customizations are applied.
admin.site.register(User, CustomUserAdmin)
