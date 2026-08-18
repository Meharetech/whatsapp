from models.user import User
from extensions import db
from werkzeug.security import generate_password_hash
from datetime import datetime

def create_default_users():
    """Create default users if they don't exist"""
    try:
        # Check if default users already exist by both username and email
        existing_user = User.query.filter_by(username='Admin').first() or User.query.filter_by(email='user@whatsapp-ui.com').first()
        existing_admin = User.query.filter_by(username='Adminpro').first() or User.query.filter_by(email='admin@whatsapp-ui.com').first()
        
        if existing_user and existing_admin:
            return
        
        # Create default user if it doesn't exist
        if not existing_user:
            user = User(
                username='Admin',
                email='user@whatsapp-ui.com',
                password='Admin@meta123',
                role='user',
                first_name='Default',
                last_name='User',
                is_verified=True
            )
            db.session.add(user)
        
        # Create default admin if it doesn't exist
        if not existing_admin:
            admin = User(
                username='Adminpro',
                email='admin@whatsapp-ui.com',
                password='Admin@meta123',
                role='admin',
                first_name='System',
                last_name='Administrator',
                is_verified=True
            )
            db.session.add(admin)
        
        db.session.commit()
        
    except Exception as e:
        db.session.rollback()
        print(f"Error creating default users: {str(e)}")

def create_user(username, email, password, role='user', **kwargs):
    """Create a new user"""
    try:
        username = username.strip() if username else ''
        email = email.strip().lower() if email else ''
        
        if not username or not email or not password:
            return False, "Username, email, and password are required"

        # Check if user already exists
        if User.query.filter_by(username=username).first():
            return False, "Username already exists"
        
        if User.query.filter_by(email=email).first():
            return False, "Email already registered"
        
        # Create new user
        user = User(
            username=username,
            email=email,
            password=password,
            role=role,
            **kwargs
        )
        
        db.session.add(user)
        db.session.commit()
        
        # Send welcome email
        try:
            from utils.email import send_welcome_email, send_user_registration_notification
            send_welcome_email(email, username)
            # Also send notification to admin
            send_user_registration_notification("rahulverma9466105@gmail.com", username)
        except Exception as e:
            print(f"Warning: Failed to send welcome email: {str(e)}")
        
        return True, f"User {username} created successfully"
        
    except Exception as e:
        db.session.rollback()
        return False, f"Error creating user: {str(e)}"

def authenticate_user(username_or_email, password, required_role=None):
    """
    Authenticate user with username or email and password.
    Returns (success, user_or_message)
    """
    try:
        identifier = username_or_email.strip()
        user = User.query.filter(
            (User.username == identifier) | (User.email == identifier.lower())
        ).first()
        
        if not user:
            return False, "User not found"
        
        if not user.is_active:
            return False, "Account is deactivated"
        
        if not user.check_password(password):
            return False, "Invalid password"
            
        if required_role and user.role != required_role:
            return False, f"User does not have required '{required_role}' role"
            
        return True, user
    except Exception as e:
        return False, f"Authentication error: {str(e)}"

def get_user_by_id(user_id):
    """Retrieve user object by user_id"""
    try:
        return User.query.get(user_id)
    except Exception as e:
        return None

def get_user_by_identifier(identifier):
    """Retrieve user object by username or email"""
    try:
        identifier = identifier.strip()
        return User.query.filter(
            (User.username == identifier) | (User.email == identifier.lower())
        ).first()
    except Exception as e:
        return None

def update_user_profile(user_id, **kwargs):
    """Update user profile information"""
    try:
        user = User.query.get(user_id)
        if not user:
            return False, "User not found"
        
        # Update allowed fields
        allowed_fields = ['first_name', 'last_name', 'phone', 'avatar', 'email', 'username']
        for field, value in kwargs.items():
            if field in allowed_fields and value is not None:
                if field == 'email':
                    value = value.strip().lower()
                    existing = User.query.filter(User.email == value, User.id != user_id).first()
                    if existing:
                        return False, "Email already in use by another user"
                elif field == 'username':
                    value = value.strip()
                    existing = User.query.filter(User.username == value, User.id != user_id).first()
                    if existing:
                        return False, "Username already in use by another user"
                setattr(user, field, value)
        
        user.updated_at = datetime.utcnow()
        db.session.commit()
        return True, "Profile updated successfully"
        
    except Exception as e:
        db.session.rollback()
        return False, f"Error updating profile: {str(e)}"

def change_user_password(user_id, current_password, new_password):
    """Change user password after validating current password"""
    try:
        user = User.query.get(user_id)
        if not user:
            return False, "User not found"
        
        if not user.check_password(current_password):
            return False, "Current password is incorrect"
        
        user.set_password(new_password)
        user.updated_at = datetime.utcnow()
        db.session.commit()
        
        return True, "Password changed successfully"
        
    except Exception as e:
        db.session.rollback()
        return False, f"Error changing password: {str(e)}"

def reset_user_password(user_id, new_password):
    """Admin-initiated password reset without requiring current password"""
    try:
        user = User.query.get(user_id)
        if not user:
            return False, "User not found"
            
        user.set_password(new_password)
        user.updated_at = datetime.utcnow()
        db.session.commit()
        
        return True, f"Password for {user.username} reset successfully"
    except Exception as e:
        db.session.rollback()
        return False, f"Error resetting password: {str(e)}"

def deactivate_user(user_id):
    """Deactivate a user account"""
    try:
        user = User.query.get(user_id)
        if not user:
            return False, "User not found"
        
        user.is_active = False
        user.updated_at = datetime.utcnow()
        db.session.commit()
        
        return True, f"User {user.username} deactivated successfully"
        
    except Exception as e:
        db.session.rollback()
        return False, f"Error deactivating user: {str(e)}"

def activate_user(user_id):
    """Activate a user account"""
    try:
        user = User.query.get(user_id)
        if not user:
            return False, "User not found"
        
        user.is_active = True
        user.updated_at = datetime.utcnow()
        db.session.commit()
        
        return True, f"User {user.username} activated successfully"
        
    except Exception as e:
        db.session.rollback()
        return False, f"Error activating user: {str(e)}"

def verify_user(user_id):
    """Mark user account as verified"""
    try:
        user = User.query.get(user_id)
        if not user:
            return False, "User not found"
            
        user.is_verified = True
        user.updated_at = datetime.utcnow()
        db.session.commit()
        
        return True, f"User {user.username} verified successfully"
    except Exception as e:
        db.session.rollback()
        return False, f"Error verifying user: {str(e)}"

def update_user_role(user_id, new_role):
    """Update user role ('user' or 'admin')"""
    try:
        if new_role not in ['user', 'admin']:
            return False, "Invalid role. Role must be 'user' or 'admin'"
            
        user = User.query.get(user_id)
        if not user:
            return False, "User not found"
            
        user.role = new_role
        user.updated_at = datetime.utcnow()
        db.session.commit()
        
        return True, f"User role for {user.username} updated to '{new_role}'"
    except Exception as e:
        db.session.rollback()
        return False, f"Error updating role: {str(e)}"

def delete_user(user_id):
    """Delete user account"""
    try:
        user = User.query.get(user_id)
        if not user:
            return False, "User not found"
            
        username = user.username
        db.session.delete(user)
        db.session.commit()
        
        return True, f"User {username} deleted successfully"
    except Exception as e:
        db.session.rollback()
        return False, f"Error deleting user: {str(e)}"

def get_all_users(page=1, per_page=20, search=None, role=None, is_active=None):
    """
    Get paginated user list with optional search query and filters
    """
    try:
        query = User.query
        
        if search:
            search_term = f"%{search.strip()}%"
            query = query.filter(
                (User.username.ilike(search_term)) | 
                (User.email.ilike(search_term)) |
                (User.first_name.ilike(search_term)) |
                (User.last_name.ilike(search_term))
            )
            
        if role:
            query = query.filter(User.role == role)
            
        if is_active is not None:
            query = query.filter(User.is_active == bool(is_active))
            
        paginated_users = query.order_by(User.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        return {
            'users': [user.to_dict() for user in paginated_users.items],
            'pagination': {
                'page': paginated_users.page,
                'pages': paginated_users.pages,
                'per_page': paginated_users.per_page,
                'total': paginated_users.total
            }
        }
    except Exception as e:
        print(f"Error fetching user list: {str(e)}")
        return None

def get_user_stats(user_id):
    """Get detailed user statistics"""
    try:
        user = User.query.get(user_id)
        if not user:
            return None
        
        # Get user's groups count
        groups_count = user.groups.count() if hasattr(user, 'groups') and user.groups else 0
        
        # Get user's messages count
        messages_count = user.messages.count() if hasattr(user, 'messages') and user.messages else 0
        
        # Get user's scheduled posts count if relationship exists
        scheduled_posts_count = len(user.scheduled_posts) if hasattr(user, 'scheduled_posts') and user.scheduled_posts else 0

        return {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'role': user.role,
            'is_active': user.is_active,
            'is_verified': user.is_verified,
            'groups_count': groups_count,
            'messages_count': messages_count,
            'scheduled_posts_count': scheduled_posts_count,
            'created_at': user.created_at.isoformat() if user.created_at else None,
            'last_login': user.last_login.isoformat() if user.last_login else None
        }
        
    except Exception as e:
        print(f"Error getting user stats: {str(e)}")
        return None

def get_system_user_summary():
    """Get system-wide user counts and statistics"""
    try:
        total_users = User.query.count()
        active_users = User.query.filter_by(is_active=True).count()
        admin_count = User.query.filter_by(role='admin').count()
        regular_user_count = User.query.filter_by(role='user').count()
        verified_count = User.query.filter_by(is_verified=True).count()

        return {
            'total_users': total_users,
            'active_users': active_users,
            'inactive_users': total_users - active_users,
            'admins': admin_count,
            'regular_users': regular_user_count,
            'verified_users': verified_count
        }
    except Exception as e:
        print(f"Error getting system user summary: {str(e)}")
        return None
