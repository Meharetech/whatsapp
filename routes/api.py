from flask import Blueprint, request, jsonify, send_file
from flask_login import login_required, current_user
from functools import wraps
from extensions import db
from models.user import User, Group, Message
from models.assembly import Assembly
from datetime import datetime
import os
import json

api_bp = Blueprint('api', __name__)

def admin_required(f):
    """Decorator to require admin role for API endpoints"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin():
            return jsonify({
                'success': False,
                'message': 'Admin privileges required'
            }), 403
        return f(*args, **kwargs)
    return decorated_function

# ============================================================================
# DASHBOARD STATISTICS API
# ============================================================================

@api_bp.route('/stats')
@login_required
def api_stats():
    """API endpoint for dashboard statistics"""
    from utils.dashboard_utils import get_dashboard_stats
    stats = get_dashboard_stats(current_user.id, current_user.role)
    return jsonify(stats)

@api_bp.route('/check-session', methods=['GET'])
@login_required
def check_session():
    """Check if user session is valid"""
    return jsonify({
        'success': True,
        'user_id': current_user.id,
        'username': current_user.username,
        'role': current_user.role
    })

# ============================================================================
# ASSEMBLY MANAGEMENT API
# ============================================================================

@api_bp.route('/assemblies', methods=['GET'])
@login_required
def get_assemblies():
    """Get all assemblies"""
    try:
        from models.assembly import Assembly
        
        assemblies = Assembly.query.filter_by(is_active=True).all()
        assemblies_data = [{
            'id': assembly.id,
            'name': assembly.name
        } for assembly in assemblies]
        
        return jsonify({
            'success': True,
            'assemblies': assemblies_data
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@api_bp.route('/assemblies', methods=['POST'])
@login_required
@admin_required
def create_assembly():
    """Create a new assembly"""
    try:
        data = request.get_json()
        name = data.get('name', '').strip()
        remarks = data.get('remarks', '').strip()
        
        if not name:
            return jsonify({
                'success': False,
                'message': 'Assembly name is required'
            }), 400
        
        # Check if assembly name already exists
        existing_assembly = Assembly.query.filter_by(name=name).first()
        if existing_assembly:
            return jsonify({
                'success': False,
                'message': 'Assembly name already exists'
            }), 400
        
        # Create new assembly
        assembly = Assembly(
            name=name,
            remarks=remarks,
            created_by_id=current_user.id
        )
        
        db.session.add(assembly)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Assembly created successfully',
            'assembly': assembly.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@api_bp.route('/assemblies/<int:assembly_id>', methods=['GET'])
@login_required
@admin_required
def get_assembly(assembly_id):
    """Get specific assembly details"""
    try:
        assembly = Assembly.query.get_or_404(assembly_id)
        return jsonify({
            'success': True,
            'assembly': assembly.to_dict()
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@api_bp.route('/assemblies/<int:assembly_id>', methods=['PUT'])
@login_required
@admin_required
def update_assembly(assembly_id):
    """Update assembly details"""
    try:
        assembly = Assembly.query.get_or_404(assembly_id)
        data = request.get_json()
        
        if 'name' in data:
            assembly.name = data['name'].strip()
        if 'remarks' in data:
            assembly.remarks = data['remarks'].strip()
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Assembly updated successfully',
            'assembly': assembly.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@api_bp.route('/assemblies/<int:assembly_id>', methods=['DELETE'])
@login_required
@admin_required
def delete_assembly(assembly_id):
    """Permanently delete an assembly and all associated data, groups, files, and scheduled posts"""
    try:
        import shutil
        from models.user import PostSchedule, PostScheduleGroup
        
        assembly = Assembly.query.get_or_404(assembly_id)
        assembly_name = assembly.name
        
        # 1. Delete associated PostSchedule & PostScheduleGroup records
        scheduled_posts = PostSchedule.query.filter_by(assembly_id=assembly.id).all()
        for post in scheduled_posts:
            # Delete media files from disk if any
            for file_attr in ['image_file', 'audio_file', 'video_file', 'completion_file']:
                file_rel = getattr(post, file_attr, None)
                if file_rel:
                    full_path = os.path.join('database', file_rel)
                    if os.path.exists(full_path) and os.path.isfile(full_path):
                        try:
                            os.remove(full_path)
                        except Exception:
                            pass
            db.session.delete(post)
            
        # Delete PostScheduleGroup entries matching assembly_name
        PostScheduleGroup.query.filter_by(assembly_name=assembly_name).delete(synchronize_session=False)
        
        # 2. Hard delete the Assembly record itself from database
        db.session.delete(assembly)
        db.session.commit()
        
        # 3. Purge all physical folders and files from disk
        possible_dirs = [
            os.path.join('database', assembly_name),
            os.path.join('uploads', assembly_name),
            os.path.join('uploads', f'assembly_{assembly_name}'),
            os.path.join('static', 'assembly_excel', assembly_name),
            os.path.join('excel_files', assembly_name),
            os.path.join('csv_files', assembly_name)
        ]
        
        for dir_path in possible_dirs:
            if os.path.exists(dir_path):
                try:
                    if os.path.isdir(dir_path):
                        shutil.rmtree(dir_path)
                    else:
                        os.remove(dir_path)
                except Exception as err:
                    print(f"Warning: Could not remove directory/file {dir_path}: {err}")
                    
        return jsonify({
            'success': True,
            'message': f'Assembly "{assembly_name}" and all associated group details, files, and materials were permanently deleted.'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Failed to delete assembly: {str(e)}'
        }), 500

# ============================================================================
# USER MANAGEMENT API
# ============================================================================

@api_bp.route('/users', methods=['GET'])
@login_required
@admin_required
def get_users():
    """Get all users (admin only)"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        
        users = User.query.paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        return jsonify({
            'success': True,
            'users': [user.to_dict() for user in users.items],
            'pagination': {
                'page': users.page,
                'pages': users.pages,
                'per_page': users.per_page,
                'total': users.total
            }
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@api_bp.route('/users/<int:user_id>', methods=['GET'])
@login_required
@admin_required
def get_user(user_id):
    """Get specific user details (admin only)"""
    try:
        user = User.query.get_or_404(user_id)
        return jsonify({
            'success': True,
            'user': user.to_dict()
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

# ============================================================================
# GROUP MANAGEMENT API
# ============================================================================

@api_bp.route('/groups', methods=['GET'])
@login_required
@admin_required
def get_groups():
    """Get all groups (admin only)"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        
        groups = Group.query.paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        return jsonify({
            'success': True,
            'groups': [group.to_dict() for group in groups.items],
            'pagination': {
                'page': groups.page,
                'pages': groups.pages,
                'per_page': groups.per_page,
                'total': groups.total
            }
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

# ============================================================================
# MESSAGE MANAGEMENT API
# ============================================================================

@api_bp.route('/messages', methods=['GET'])
@login_required
@admin_required
def get_messages():
    """Get all messages (admin only)"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        
        messages = Message.query.paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        return jsonify({
            'success': True,
            'messages': [message.to_dict() for message in messages.items],
            'pagination': {
                'page': messages.page,
                'pages': messages.pages,
                'per_page': messages.per_page,
                'total': messages.total
            }
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

# ============================================================================
# REPORT UPLOAD API
# ============================================================================

@api_bp.route('/upload-groups', methods=['POST'])
@login_required
@admin_required
def upload_groups():
    """Upload group files to specified assembly"""
    try:
        # Get form data
        assembly_name = request.form.get('assembly_name', '').strip()
        
        if not assembly_name:
            return jsonify({
                'success': False,
                'message': 'Missing required field: assembly_name'
            }), 400
        
        # Check if files were uploaded
        if 'files[]' not in request.files:
            return jsonify({
                'success': False,
                'message': 'No files were uploaded'
            }), 400
        
        files = request.files.getlist('files[]')
        if not files or all(f.filename == '' for f in files):
            return jsonify({
                'success': False,
                'message': 'No files were selected'
            }), 400
        
        # Filter valid files
        valid_files = []
        for file in files:
            if file and file.filename:
                valid_files.append(file)
        
        if not valid_files:
            return jsonify({
                'success': False,
                'message': 'No valid files found'
            }), 400
        
        # Create or get assembly
        assembly = Assembly.query.filter_by(name=assembly_name).first()
        if not assembly:
            # Create new assembly
            assembly = Assembly(
                name=assembly_name,
                remarks=f'Created via group upload',
                created_by_id=current_user.id
            )
            db.session.add(assembly)
            db.session.commit()
        
        # Create directory structure
        import os
        
        # Create base directory path: database/<assembly_name>/groups/
        base_dir = os.path.join('database', assembly_name, 'groups')
        os.makedirs(base_dir, exist_ok=True)
        
        # Save files
        saved_files = []
        for file in valid_files:
            if file and file.filename:
                # Generate unique filename
                filename = file.filename
                counter = 1
                while os.path.exists(os.path.join(base_dir, filename)):
                    name, ext = os.path.splitext(file.filename)
                    filename = f"{name}_{counter}{ext}"
                    counter += 1
                
                # Save file
                file_path = os.path.join(base_dir, filename)
                file.save(file_path)
                saved_files.append(filename)
        
        return jsonify({
            'success': True,
            'message': f'Successfully uploaded {len(saved_files)} files to {assembly_name}/groups/',
            'files_saved': saved_files,
            'assembly_id': assembly.id,
            'target_path': f'{assembly_name}/groups/'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Upload failed: {str(e)}'
        }), 500

# ============================================================================
# REPORT UPLOAD API
# ============================================================================

@api_bp.route('/upload-reports', methods=['POST'])
@login_required
@admin_required
def upload_reports():
    """Upload JSON reports to specified assembly and folder"""
    try:
        print("=== UPLOAD REPORTS DEBUG START ===")
        
        # Get form data
        assembly_name = request.form.get('assembly_name', '').strip()
        target_date = request.form.get('target_date', '').strip()
        folder_type = request.form.get('folder_type', '').strip()
        
        print(f"DEBUG: assembly_name = '{assembly_name}'")
        print(f"DEBUG: target_date = '{target_date}'")
        print(f"DEBUG: folder_type = '{folder_type}'")
        
        if not all([assembly_name, target_date, folder_type]):
            return jsonify({
                'success': False,
                'message': 'Missing required fields: assembly_name, target_date, folder_type'
            }), 400
        
        # Validate folder type
        valid_folder_types = ['messages', 'images', 'audio', 'video', 'urls']
        if folder_type not in valid_folder_types:
            return jsonify({
                'success': False,
                'message': f'Invalid folder type. Must be one of: {", ".join(valid_folder_types)}'
            }), 400
        
        # Check if files were uploaded
        if 'files[]' not in request.files:
            return jsonify({
                'success': False,
                'message': 'No files were uploaded'
            }), 400
        
        files = request.files.getlist('files[]')
        if not files or all(f.filename == '' for f in files):
            return jsonify({
                'success': False,
                'message': 'No files were selected'
            }), 400
        
        # Validate file types
        json_files = []
        for file in files:
            if file and file.filename:
                if not file.filename.lower().endswith('.json'):
                    return jsonify({
                        'success': False,
                        'message': f'File {file.filename} is not a JSON file'
                    }), 400
                json_files.append(file)
        
        if not json_files:
            return jsonify({
                'success': False,
                'message': 'No valid JSON files found'
            }), 400
        
        # Create or get assembly
        assembly = Assembly.query.filter_by(name=assembly_name).first()
        if not assembly:
            # Create new assembly
            assembly = Assembly(
                name=assembly_name,
                remarks=f'Created via report upload on {target_date}',
                created_by_id=current_user.id
            )
            db.session.add(assembly)
            db.session.commit()
        
        # Create directory structure
        import os
        from datetime import datetime
        
        # Parse target date
        try:
            date_obj = datetime.strptime(target_date, '%Y-%m-%d')
            print(f"DEBUG: Parsed date_obj = {date_obj}")
        except ValueError:
            print(f"DEBUG: Date parsing failed for '{target_date}'")
            return jsonify({
                'success': False,
                'message': 'Invalid date format. Use YYYY-MM-DD'
            }), 400
        
        # Use the selected date directly (no backdate calculation)
        folder_date = target_date
        print(f"DEBUG: folder_date = '{folder_date}' (should be same as target_date)")
        
        # Create base directory path using the selected date
        base_dir = os.path.join('database', assembly_name, folder_date, folder_type)
        print(f"DEBUG: base_dir = '{base_dir}'")
        os.makedirs(base_dir, exist_ok=True)
        
        # Save files
        saved_files = []
        for file in json_files:
            if file and file.filename:
                # Generate unique filename
                filename = file.filename
                counter = 1
                while os.path.exists(os.path.join(base_dir, filename)):
                    name, ext = os.path.splitext(file.filename)
                    filename = f"{name}_{counter}{ext}"
                    counter += 1
                
                # Save file
                file_path = os.path.join(base_dir, filename)
                file.save(file_path)
                saved_files.append(filename)
        
        print(f"DEBUG: Final response - selected_date: '{target_date}', folder_date: '{folder_date}'")
        print(f"DEBUG: Files saved in: {base_dir}")
        print("=== UPLOAD REPORTS DEBUG END ===")
        
        return jsonify({
            'success': True,
            'message': f'Successfully uploaded {len(saved_files)} files to {assembly_name}/{folder_date}/{folder_type}/',
            'files_saved': saved_files,
            'assembly_id': assembly.id,
            'target_path': f'{assembly_name}/{folder_date}/{folder_type}/',
            'selected_date': target_date,
            'folder_date': folder_date
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Upload failed: {str(e)}'
        }), 500

# ============================================================================
# ASSEMBLY FILES LIST & DELETE API
# ============================================================================

@api_bp.route('/assembly-files/<assembly_name>', methods=['GET'])
@login_required
@admin_required
def get_assembly_files(assembly_name):
    """List all group files (original and converted) for a specific assembly"""
    try:
        # Sanitize assembly name to prevent directory traversal
        assembly_name = os.path.basename(assembly_name)
        assembly_path = os.path.join('database', assembly_name, 'groups')
        
        files = []
        if os.path.exists(assembly_path):
            for filename in os.listdir(assembly_path):
                file_path = os.path.join(assembly_path, filename)
                if os.path.isfile(file_path):
                    file_stat = os.stat(file_path)
                    files.append({
                        'filename': filename,
                        'size': file_stat.st_size,
                        'last_modified': datetime.fromtimestamp(file_stat.st_mtime).isoformat()
                    })
        
        # Sort files by last modified date (newest first)
        files.sort(key=lambda x: x['last_modified'], reverse=True)
        
        return jsonify({
            'success': True,
            'files': files
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@api_bp.route('/assembly-files/<assembly_name>/<filename>', methods=['DELETE'])
@login_required
@admin_required
def delete_assembly_file(assembly_name, filename):
    """Delete a specific group file from the assembly"""
    try:
        # Sanitize parameters to prevent path traversal
        assembly_name = os.path.basename(assembly_name)
        filename = os.path.basename(filename)
        
        file_path = os.path.join('database', assembly_name, 'groups', filename)
        
        if not os.path.exists(file_path):
            return jsonify({
                'success': False,
                'message': 'File not found'
            }), 404
            
        os.remove(file_path)
        
        return jsonify({
            'success': True,
            'message': f'File {filename} deleted successfully'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

# ============================================================================
# POST SCHEDULING API
# ============================================================================

@api_bp.route('/assemblies-with-groups', methods=['GET'])
@login_required
def get_assemblies_with_groups():
    """Get all assemblies with their available CSV files in groups folder"""
    try:
        import os
        
        assemblies_data = []
        
        # Get all assemblies from database
        assemblies = Assembly.query.filter_by(is_active=True).all()
        
        for assembly in assemblies:
            assembly_path = os.path.join('database', assembly.name, 'groups')
            
            if os.path.exists(assembly_path):
                csv_files = []
                
                # Get all CSV files in the groups folder
                for filename in os.listdir(assembly_path):
                    if filename.lower().endswith('.csv'):
                        csv_files.append(filename)
                
                assemblies_data.append({
                    'id': assembly.id,
                    'name': assembly.name,
                    'csv_files': csv_files,
                    'total_files': len(csv_files)
                })
            else:
                # Assembly exists but no groups folder
                assemblies_data.append({
                    'id': assembly.id,
                    'name': assembly.name,
                    'csv_files': [],
                    'total_files': 0
                })
        
        return jsonify({
            'success': True,
            'assemblies': assemblies_data
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@api_bp.route('/create-scheduled-post', methods=['POST'])
@login_required
def create_scheduled_post():
    """Create a new scheduled post"""
    try:
        from models.user import PostSchedule, PostScheduleGroup
        from datetime import datetime
        
        # Get form data
        title = request.form.get('title', '').strip()
        message_text = request.form.get('message_text', '').strip()
        scheduled_date = request.form.get('scheduled_date', '').strip()
        scheduled_time = request.form.get('scheduled_time', '').strip()
        assembly_id = request.form.get('assembly_id', '').strip()
        selected_groups = request.form.getlist('selected_groups[]')
        
        # Validation
        if not all([title, scheduled_date, scheduled_time, assembly_id, selected_groups]):
            return jsonify({
                'success': False,
                'message': 'Missing required fields'
            }), 400
        
        # Parse date and time
        try:
            date_obj = datetime.strptime(scheduled_date, '%Y-%m-%d').date()
            time_obj = datetime.strptime(scheduled_time, '%H:%M').time()
        except ValueError:
            return jsonify({
                'success': False,
                'message': 'Invalid date or time format'
            }), 400
        
        # Check if assembly exists
        assembly = Assembly.query.get(assembly_id)
        if not assembly:
            return jsonify({
                'success': False,
                'message': 'Assembly not found'
            }), 404
        
        # Handle file uploads
        audio_file = None
        video_file = None
        image_file = None
        
        if 'audio_file' in request.files and request.files['audio_file'].filename:
            audio_file = save_uploaded_file(request.files['audio_file'], 'audio', assembly.name)
        
        if 'video_file' in request.files and request.files['video_file'].filename:
            video_file = save_uploaded_file(request.files['video_file'], 'video', assembly.name)
        
        if 'image_file' in request.files and request.files['image_file'].filename:
            image_file = save_uploaded_file(request.files['image_file'], 'image', assembly.name)
        
        # Create scheduled post
        scheduled_post = PostSchedule(
            title=title,
            message_text=message_text,
            audio_file=audio_file,
            video_file=video_file,
            image_file=image_file,
            scheduled_date=date_obj,
            scheduled_time=time_obj,
            created_by_id=current_user.id,
            assembly_id=assembly.id
        )
        
        db.session.add(scheduled_post)
        db.session.flush()  # Get the ID
        
        # Add target groups
        for group_name in selected_groups:
            group_schedule = PostScheduleGroup(
                post_schedule_id=scheduled_post.id,
                group_name=group_name,
                assembly_name=assembly.name
            )
            db.session.add(group_schedule)
        
        db.session.commit()
        
        # Send email notifications
        try:
            from utils.email import send_post_scheduled_notification, send_admin_post_notification, send_new_post_notification_to_all_emails
            
            # Prepare post data for email notifications
            post_data = {
                'title': title,
                'scheduled_date': scheduled_date,
                'scheduled_time': scheduled_time,
                'assembly_name': assembly.name,
                'group_count': len(selected_groups),
                'message_preview': message_text[:100] + ('...' if len(message_text) > 100 else ''),
                'media_files': 'None' if not any([image_file, audio_file, video_file]) else ', '.join(filter(None, [
                    'Image' if image_file else None,
                    'Audio' if audio_file else None,
                    'Video' if video_file else None
                ])),
                'post_id': scheduled_post.id,
                'username': current_user.username,
                'user_email': current_user.email
            }
            
            # Send notification to the user who created the post
            send_post_scheduled_notification(current_user.email, current_user.username, post_data)
            
            # Send notification to admin
            send_admin_post_notification("rahulverma9466105@gmail.com", post_data)
            
            # Send notification to all emails in email.csv
            # Prepare data for the new post notification format
            new_post_data = {
                'title': title,
                'sent_date': scheduled_date,
                'sent_time': scheduled_time,
                'assembly_name': assembly.name,
                'group_count': len(selected_groups),
                'username': current_user.username,
                'post_id': scheduled_post.id,
                'message': message_text,
                'media_files': 'None' if not any([image_file, audio_file, video_file]) else ', '.join(filter(None, [
                    'Image' if image_file else None,
                    'Audio' if audio_file else None,
                    'Video' if video_file else None
                ])),
                'groups_reached': len(selected_groups),
                'delivery_time': 'Scheduled'
            }
            
            # Send notification to all emails in email.csv
            send_new_post_notification_to_all_emails(new_post_data)
            
        except Exception as e:
            print(f"Warning: Failed to send email notifications: {str(e)}")
        
        return jsonify({
            'success': True,
            'message': 'Scheduled post created successfully',
            'post_id': scheduled_post.id
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Failed to create scheduled post: {str(e)}'
        }), 500

@api_bp.route('/scheduled-posts', methods=['GET'])
@login_required
def get_scheduled_posts():
    """Get all scheduled posts for the current user"""
    try:
        from models.user import PostSchedule
        
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        
        # Get posts created by current user
        posts = PostSchedule.query.filter_by(created_by_id=current_user.id).order_by(
            PostSchedule.scheduled_date.desc(), PostSchedule.scheduled_time.desc()
        ).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        return jsonify({
            'success': True,
            'posts': [post.to_dict() for post in posts.items],
            'pagination': {
                'page': posts.page,
                'pages': posts.pages,
                'per_page': posts.per_page,
                'total': posts.total
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@api_bp.route('/scheduled-posts/<int:post_id>/status', methods=['PUT'])
@login_required
def update_post_status(post_id):
    """Update the status of a scheduled post"""
    try:
        from models.user import PostSchedule
        
        post = PostSchedule.query.get_or_404(post_id)
        
        if post.created_by_id != current_user.id and not current_user.is_admin():
            return jsonify({
                'success': False,
                'message': 'You can only update your own posts'
            }), 403
        
        # Get form data (supports both JSON and form data)
        if request.is_json:
            data = request.get_json()
            new_status = data.get('status', '').strip()
            admin_notes = data.get('admin_notes', '').strip()
        else:
            new_status = request.form.get('status', '').strip()
            admin_notes = request.form.get('admin_notes', '').strip()
        
        valid_statuses = ['pending', 'running', 'completed', 'failed', 'cancelled']
        if new_status not in valid_statuses:
            return jsonify({
                'success': False,
                'message': f'Invalid status. Must be one of: {", ".join(valid_statuses)}'
            }), 400
        
        # Update status and admin notes
        post.status = new_status
        if admin_notes:
            post.admin_notes = admin_notes
        
        # Handle completion file upload
        if new_status == 'completed' and 'completion_file' in request.files:
            completion_file = request.files['completion_file']
            if completion_file and completion_file.filename:
                try:
                    # Save completion file using the assembly relationship
                    if post.assembly and post.assembly.name:
                        file_path = save_completion_file(completion_file, post.assembly.name)
                        post.completion_file = file_path
                    else:
                        # Fallback: get assembly name from assembly_id
                        from models.assembly import Assembly
                        assembly = Assembly.query.get(post.assembly_id)
                        if assembly:
                            file_path = save_completion_file(completion_file, assembly.name)
                            post.completion_file = file_path
                        else:
                            return jsonify({
                                'success': False,
                                'message': 'Assembly not found for this post'
                            }), 404
                except Exception as e:
                    return jsonify({
                        'success': False,
                        'message': f'Error saving completion file: {str(e)}'
                    }), 500
        
        # Handle special status updates
        if new_status == 'completed':
            post.sent_at = datetime.utcnow()
            post.is_sent = True
        elif new_status == 'running':
            post.updated_at = datetime.utcnow()
        
        # Always update the updated_at timestamp
        post.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        # Send email notifications for status changes
        try:
            from utils.email import send_post_status_notification, send_admin_post_failed_notification, send_new_post_notification_to_all_emails
            
            # Get user who created the post
            post_creator = User.query.get(post.created_by_id)
            
            if post_creator and new_status in ['completed', 'failed', 'cancelled']:
                # Prepare post data for email notifications
                post_data = {
                    'title': post.title,
                    'assembly_name': post.assembly.name if post.assembly else 'N/A',
                    'completed_at': post.sent_at.strftime('%Y-%m-%d %H:%M:%S') if post.sent_at else 'N/A',
                    'admin_notes': post.admin_notes,
                    'username': post_creator.username,
                    'user_email': post_creator.email,
                    'post_id': post.id
                }
                
                # Send notification to post creator
                send_post_status_notification(post_creator.email, post_creator.username, post_data, new_status)
                
                # Also send notification to admin for failed posts
                if new_status == 'failed':
                    send_admin_post_failed_notification("rahulverma9466105@gmail.com", post_data)
                
                # Send notification to all emails in email.csv when post is completed
                if new_status == 'completed':
                    # Prepare additional data for the new post notification
                    completed_post_data = {
                        'title': post.title,
                        'sent_date': post.sent_at.strftime('%Y-%m-%d') if post.sent_at else 'N/A',
                        'sent_time': post.sent_at.strftime('%H:%M:%S') if post.sent_at else 'N/A',
                        'assembly_name': post.assembly.name if post.assembly else 'N/A',
                        'group_count': post.target_groups.count() if post.target_groups else 0,
                        'username': post_creator.username,
                        'post_id': post.id,
                        'message': post.message_text or 'No message content',
                        'media_files': 'None' if not any([post.image_file, post.audio_file, post.video_file]) else ', '.join(filter(None, [
                            'Image' if post.image_file else None,
                            'Audio' if post.audio_file else None,
                            'Video' if post.video_file else None
                        ])),
                        'groups_reached': post.target_groups.count() if post.target_groups else 0,
                        'delivery_time': 'Immediate' if post.sent_at else 'N/A'
                    }
                    
                    # Send notification to all emails in email.csv
                    send_new_post_notification_to_all_emails(completed_post_data)
                
        except Exception as e:
            print(f"Warning: Failed to send status update email notifications: {str(e)}")
        
        return jsonify({
            'success': True,
            'message': f'Post status updated to {new_status}',
            'post': post.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Failed to update status: {str(e)}'
        }), 500

@api_bp.route('/scheduled-posts/<int:post_id>/delete', methods=['DELETE'])
@login_required
def delete_scheduled_post(post_id):
    """Delete a scheduled post"""
    try:
        from models.user import PostSchedule
        
        post = PostSchedule.query.get_or_404(post_id)
        
        # Only allow admin or post creator to delete
        if post.created_by_id != current_user.id and not current_user.is_admin():
            return jsonify({
                'success': False,
                'message': 'You can only delete your own posts'
            }), 403
        
        # Get post details for email notification
        post_details = {
            'title': post.title,
            'assembly_name': post.assembly.name if post.assembly else 'N/A',
            'username': post.created_by.username if post.created_by else 'Unknown',
            'user_email': post.created_by.email if post.created_by else 'Unknown',
            'post_id': post.id
        }
        
        # Delete the post (this will cascade delete related records)
        db.session.delete(post)
        db.session.commit()
        
        # Send email notification about post deletion
        try:
            from utils.email import send_post_deletion_notification
            
            if current_user.is_admin():
                # Admin deleted the post - notify the post creator
                if post.created_by and post.created_by.email:
                    send_post_deletion_notification(
                        post.created_by.email, 
                        post.created_by.username, 
                        post_details, 
                        'admin_deleted'
                    )
            else:
                # User deleted their own post - notify admin
                send_post_deletion_notification(
                    "rahulverma9466105@gmail.com", 
                    "Admin", 
                    post_details, 
                    'user_deleted'
                )
                
        except Exception as e:
            print(f"Warning: Failed to send deletion email notifications: {str(e)}")
        
        return jsonify({
            'success': True,
            'message': 'Post deleted successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Failed to delete post: {str(e)}'
        }), 500

def save_uploaded_file(file, file_type, assembly_name):
    """Helper function to save uploaded files"""
    import os
    from werkzeug.utils import secure_filename
    
    # Create directory structure
    upload_dir = os.path.join('database', assembly_name, 'scheduled_content', file_type)
    os.makedirs(upload_dir, exist_ok=True)
    
    # Generate unique filename
    filename = secure_filename(file.filename)
    counter = 1
    while os.path.exists(os.path.join(upload_dir, filename)):
        name, ext = os.path.splitext(secure_filename(file.filename))
        filename = f"{name}_{counter}{ext}"
        counter += 1
    
    # Save file
    file_path = os.path.join(upload_dir, filename)
    file.save(file_path)
    
    # Return relative path for database storage
    return os.path.join(assembly_name, 'scheduled_content', file_type, filename)

def save_completion_file(file, assembly_name):
    """Helper function to save completion files (Excel/CSV)"""
    import os
    from werkzeug.utils import secure_filename
    
    # Create directory structure for completion files
    upload_dir = os.path.join('database', assembly_name, 'completion_files')
    os.makedirs(upload_dir, exist_ok=True)
    
    # Generate unique filename
    filename = secure_filename(file.filename)
    counter = 1
    while os.path.exists(os.path.join(upload_dir, filename)):
        name, ext = os.path.splitext(secure_filename(file.filename))
        filename = f"{name}_{counter}{ext}"
        counter += 1
    
    # Save file
    file_path = os.path.join(upload_dir, filename)
    file.save(file_path)
    
    # Return relative path for database storage
    return os.path.join(assembly_name, 'completion_files', filename)

# ============================================================================
# SYSTEM HEALTH API
# ============================================================================

@api_bp.route('/health')
def health_check():
    """System health check endpoint"""
    try:
        # Check database connection
        db.session.execute('SELECT 1')
        
        return jsonify({
            'success': True,
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'message': 'API is working correctly'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500

@api_bp.route('/test')
def test_endpoint():
    """Test endpoint to verify API is accessible"""
    return jsonify({
        'success': True,
        'message': 'API endpoint is accessible',
        'timestamp': datetime.utcnow().isoformat()
    })

@api_bp.route('/admin/all-scheduled-posts', methods=['GET'])
@login_required
@admin_required
def get_all_scheduled_posts():
    """Get all scheduled posts from all users (admin only)"""
    try:
        from models.user import PostSchedule, User
        from models.assembly import Assembly
        
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        status_filter = request.args.get('status', '').strip()
        assembly_filter = request.args.get('assembly', '').strip()
        date_filter = request.args.get('date', '').strip()
        
        # Build query with joins to get user and assembly info
        query = db.session.query(PostSchedule, User.username, User.email, Assembly.name.label('assembly_name')).join(
            User, PostSchedule.created_by_id == User.id
        ).join(
            Assembly, PostSchedule.assembly_id == Assembly.id
        )
        
        # Apply filters
        if status_filter:
            query = query.filter(PostSchedule.status == status_filter)
        
        if assembly_filter:
            query = query.filter(Assembly.name == assembly_filter)
        
        if date_filter:
            query = query.filter(PostSchedule.scheduled_date == date_filter)
        
        # Order by creation date (newest first)
        query = query.order_by(PostSchedule.created_at.desc())
        
        # Paginate results
        results = query.paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        # Format posts with user info
        posts_data = []
        for post, username, email, assembly_name in results.items:
            post_dict = post.to_dict()
            post_dict['created_by_username'] = username
            post_dict['created_by_email'] = email
            post_dict['assembly_name'] = assembly_name
            posts_data.append(post_dict)
        
        return jsonify({
            'success': True,
            'posts': posts_data,
            'pagination': {
                'page': results.page,
                'pages': results.pages,
                'per_page': results.per_page,
                'total': results.total
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@api_bp.route('/admin/scheduled-posts-stats', methods=['GET'])
@login_required
@admin_required
def get_scheduled_posts_stats():
    """Get statistics for scheduled posts (admin only)"""
    try:
        from models.user import PostSchedule
        from sqlalchemy import func
        
        # Get counts by status
        status_counts = db.session.query(
            PostSchedule.status,
            func.count(PostSchedule.id)
        ).group_by(PostSchedule.status).all()
        
        # Convert to dictionary
        stats = {}
        for status, count in status_counts:
            stats[status] = count
        
        # Ensure all statuses are present
        all_statuses = ['pending', 'running', 'completed', 'failed', 'cancelled']
        for status in all_statuses:
            if status not in stats:
                stats[status] = 0
        
        # Get total count
        total_posts = sum(stats.values())
        
        return jsonify({
            'success': True,
            'stats': {
                'total': total_posts,
                'pending': stats.get('pending', 0),
                'running': stats.get('running', 0),
                'completed': stats.get('completed', 0),
                'failed': stats.get('failed', 0),
                'cancelled': stats.get('cancelled', 0)
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@api_bp.route('/admin/download-file/<int:post_id>/<file_type>', methods=['GET'])
@login_required
@admin_required
def download_scheduled_post_file(post_id, file_type):
    """Download uploaded file from scheduled post (admin only)"""
    try:
        from models.user import PostSchedule
        from models.assembly import Assembly
        import os
        
        post = PostSchedule.query.get_or_404(post_id)
        
        # Get assembly name for proper path construction
        assembly = Assembly.query.get(post.assembly_id)
        if not assembly:
            return jsonify({
                'success': False,
                'message': 'Assembly not found'
            }), 404
        
        # Determine file path based on file type
        if file_type == 'image' and post.image_file:
            relative_path = post.image_file
            filename = os.path.basename(relative_path)
        elif file_type == 'audio' and post.audio_file:
            relative_path = post.audio_file
            filename = os.path.basename(relative_path)
        elif file_type == 'video' and post.video_file:
            relative_path = post.video_file
            filename = os.path.basename(relative_path)
        else:
            return jsonify({
                'success': False,
                'message': f'No {file_type} file found for this post'
            }), 404
        
        # Construct the full file path
        # The stored path from save_uploaded_file is: assembly_name/scheduled_content/file_type/filename
        # We need to prepend 'database/' to make it: database/assembly_name/scheduled_content/file_type/filename
        
        if relative_path.startswith('database/'):
            # Path already includes database prefix
            file_path = relative_path
        else:
            # Construct the path manually by prepending 'database/'
            file_path = os.path.join('database', relative_path)
        
        # Check if file exists
        if not os.path.exists(file_path):
            return jsonify({
                'success': False,
                'message': f'File not found on server. Path: {file_path}'
            }), 404
        
        # Return file for download
        return send_file(
            file_path,
            as_attachment=True,
            download_name=filename,
            mimetype='application/octet-stream'
        )
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@api_bp.route('/admin/debug-file-paths/<int:post_id>', methods=['GET'])
@login_required
@admin_required
def debug_file_paths(post_id):
    """Debug endpoint to show file paths for troubleshooting (admin only)"""
    try:
        from models.user import PostSchedule
        from models.assembly import Assembly
        import os
        
        post = PostSchedule.query.get_or_404(post_id)
        assembly = Assembly.query.get(post.assembly_id)
        
        debug_info = {
            'post_id': post_id,
            'assembly_name': assembly.name if assembly else 'N/A',
            'stored_paths': {
                'image_file': post.image_file,
                'audio_file': post.audio_file,
                'video_file': post.video_file
            },
            'constructed_paths': {},
            'file_exists': {}
        }
        
        # Check each file type
        for file_type in ['image', 'audio', 'video']:
            file_field = f'{file_type}_file'
            stored_path = getattr(post, file_field)
            
            if stored_path:
                # Construct full path
                if stored_path.startswith('database/'):
                    full_path = stored_path
                else:
                    full_path = os.path.join('database', stored_path)
                
                debug_info['constructed_paths'][file_type] = full_path
                debug_info['file_exists'][file_type] = os.path.exists(full_path)
            else:
                debug_info['constructed_paths'][file_type] = None
                debug_info['file_exists'][file_type] = False
        
        return jsonify({
            'success': True,
            'debug_info': debug_info
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@api_bp.route('/download-completion-file/<int:post_id>', methods=['GET'])
@login_required
def download_completion_file(post_id):
    """Download completion file (Excel/CSV) for a scheduled post"""
    try:
        from models.user import PostSchedule
        import os
        
        post = PostSchedule.query.get_or_404(post_id)
        
        # Check if user has access to this post
        if post.created_by_id != current_user.id and not current_user.is_admin():
            return jsonify({
                'success': False,
                'message': 'You can only download completion files for your own posts'
            }), 403
        
        if not post.completion_file:
            return jsonify({
                'success': False,
                'message': 'No completion file found for this post'
            }), 404
        
        # Construct full file path
        full_path = os.path.join('database', post.completion_file)
        
        if not os.path.exists(full_path):
            return jsonify({
                'success': False,
                'message': 'Completion file not found on server'
            }), 404
        
        # Return file for download
        filename = os.path.basename(post.completion_file)
        return send_file(
            full_path,
            as_attachment=True,
            download_name=filename,
            mimetype='application/octet-stream'
        )
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error downloading completion file: {str(e)}'
        }), 500

@api_bp.route('/dashboard-stats', methods=['GET'])
@login_required
def get_dashboard_stats():
    """Get dashboard statistics - total groups and phone numbers across assemblies"""
    try:
        import os
        import pandas as pd
        import warnings
        from pathlib import Path
        
        # Suppress pandas and openpyxl warnings
        warnings.filterwarnings('ignore', category=UserWarning, module='openpyxl')
        warnings.filterwarnings('ignore', category=UserWarning, module='pandas')
        
        database_path = 'database'
        stats = {
            'total_assemblies': 0,
            'total_groups': 0,
            'total_phones': 0,
            'assemblies': []
        }
        
        # Check if database directory exists
        if not os.path.exists(database_path):
            return jsonify({
                'success': True,
                'stats': stats
            })
        
        # Get all assembly directories
        assembly_dirs = [d for d in os.listdir(database_path) 
                        if os.path.isdir(os.path.join(database_path, d))]
        
        stats['total_assemblies'] = len(assembly_dirs)
        
        for assembly_name in assembly_dirs:
            assembly_path = os.path.join(database_path, assembly_name)
            groups_path = os.path.join(assembly_path, 'groups')
            
            assembly_stats = {
                'name': assembly_name,
                'groups_count': 0,
                'phones_count': 0,
                'groups': []
            }
            
            # Check if groups directory exists
            if os.path.exists(groups_path):
                # Get all CSV files in groups directory
                csv_files = [f for f in os.listdir(groups_path) 
                             if f.lower().endswith('.csv')]
                
                assembly_stats['groups_count'] = len(csv_files)
                stats['total_groups'] += len(csv_files)
                
                # Process each CSV file to count phone numbers
                for csv_file in csv_files:
                    file_path = os.path.join(groups_path, csv_file)
                    file_stats = {
                        'name': csv_file,
                        'phones_count': 0
                    }
                    
                    try:
                        # Read CSV file to count phone numbers with better error handling
                        # For CSV files, try different encodings
                        try:
                            df = pd.read_csv(file_path, encoding='utf-8')
                        except UnicodeDecodeError:
                            try:
                                df = pd.read_csv(file_path, encoding='latin-1')
                            except:
                                df = pd.read_csv(file_path, encoding='cp1252')
                        
                        # Look for phone number columns (common names)
                        phone_columns = []
                        for col in df.columns:
                            col_lower = str(col).lower()
                            if any(keyword in col_lower for keyword in ['phone', 'number', 'mobile', 'contact', 'whatsapp']):
                                phone_columns.append(col)
                        
                        if phone_columns:
                            # Count unique phone numbers in the first phone column found
                            phone_col = phone_columns[0]
                            # Remove empty rows and rows with all NaN values
                            df_clean = df.dropna(subset=[phone_col])
                            phone_count = df_clean[phone_col].nunique()
                            print(f"Debug: Found {phone_count} unique phone numbers in column '{phone_col}' for {csv_file}")
                        else:
                            # If no phone columns found, count rows (excluding header)
                            df_clean = df.dropna(how='all')
                            phone_count = len(df_clean)
                            
                            # If we have very few rows, it might be a header-only file
                            if phone_count <= 1:
                                phone_count = 0
                            print(f"Debug: No phone columns found, counted {phone_count} rows for {csv_file}")
                        
                        file_stats['phones_count'] = phone_count
                        assembly_stats['phones_count'] += phone_count
                        stats['total_phones'] += phone_count
                        
                    except Exception as e:
                        # If file can't be read, assume 0 phones and log error
                        file_stats['phones_count'] = 0
                        print(f"Warning: Could not read {file_path}: {str(e)}")
                        # Continue processing other files
                    
                    assembly_stats['groups'].append(file_stats)
            
            stats['assemblies'].append(assembly_stats)
        
        return jsonify({
            'success': True,
            'stats': stats
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error getting dashboard stats: {str(e)}'
        }), 500

@api_bp.route('/accurate-dashboard-stats', methods=['GET'])
@login_required
def get_accurate_dashboard_stats():
    """Get accurate dashboard statistics using the same logic as assembly-groups"""
    try:
        import os
        import pandas as pd
        import warnings
        from pathlib import Path
        
        # Suppress pandas and openpyxl warnings
        warnings.filterwarnings('ignore', category=UserWarning, module='openpyxl')
        warnings.filterwarnings('ignore', category=UserWarning, module='pandas')
        
        database_path = 'database'
        stats = {
            'total_assemblies': 0,
            'total_groups': 0,
            'total_phones': 0,
            'assemblies': []
        }
        
        # Check if database directory exists
        if not os.path.exists(database_path):
            return jsonify({
                'success': True,
                'stats': stats
            })
        
        # Get all assembly directories
        assembly_dirs = [d for d in os.listdir(database_path) 
                        if os.path.isdir(os.path.join(database_path, d))]
        
        stats['total_assemblies'] = len(assembly_dirs)
        
        for assembly_name in assembly_dirs:
            assembly_path = os.path.join(database_path, assembly_name)
            groups_path = os.path.join(assembly_path, 'groups')
            
            assembly_stats = {
                'name': assembly_name,
                'groups_count': 0,
                'phones_count': 0,
                'groups': []
            }
            
            # Check if groups directory exists
            if os.path.exists(groups_path):
                # Get all CSV files in groups directory
                csv_files = [f for f in os.listdir(groups_path) 
                             if f.lower().endswith('.csv')]
                
                assembly_stats['groups_count'] = len(csv_files)
                stats['total_groups'] += len(csv_files)
                
                # Process each CSV file to count phone numbers
                for csv_file in csv_files:
                    file_path = os.path.join(groups_path, csv_file)
                    file_stats = {
                        'name': csv_file,
                        'phones_count': 0
                    }
                    
                    try:
                        # Use the same logic as assembly-groups endpoint
                        estimated_phones = estimate_phone_count_from_file(file_path)
                        file_stats['phones_count'] = estimated_phones
                        assembly_stats['phones_count'] += estimated_phones
                        stats['total_phones'] += estimated_phones
                        
                    except Exception as e:
                        # If file can't be read, assume 0 phones and log error
                        file_stats['phones_count'] = 0
                        print(f"Warning: Could not read {file_path}: {str(e)}")
                        # Continue processing other files
                    
                    assembly_stats['groups'].append(file_stats)
            
            stats['assemblies'].append(assembly_stats)
        
        return jsonify({
            'success': True,
            'stats': stats
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error getting accurate dashboard stats: {str(e)}'
        }), 500

@api_bp.route('/get-assembly-dates/<assembly_name>', methods=['GET'])
@login_required
def get_assembly_dates(assembly_name):
    """Get all available dates for a specific assembly"""
    try:
        database_path = 'database'
        assembly_path = os.path.join(database_path, assembly_name)
        
        if not os.path.exists(assembly_path):
            return jsonify({'success': False, 'message': 'Assembly not found'}), 404
        
        date_dirs = []
        try:
            assembly_contents = os.listdir(assembly_path)
            for item in assembly_contents:
                item_path = os.path.join(assembly_path, item)
                if os.path.isdir(item_path):
                    try:
                        date_obj = datetime.strptime(item, '%Y-%m-%d')
                        date_dirs.append(item)
                    except ValueError:
                        continue
        except Exception as e:
            return jsonify({'success': False, 'message': f'Error reading assembly: {str(e)}'}), 500
        
        date_dirs.sort()
        
        return jsonify({
            'success': True,
            'assembly_name': assembly_name,
            'available_dates': date_dirs
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500

@api_bp.route('/get-assembly-messages/<assembly_name>', methods=['GET'])
@login_required
def get_assembly_messages(assembly_name):
    """Get messages from a specific assembly for group statistics"""
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        sentiment = request.args.get('sentiment', 'all')
        
        if not start_date:
            return jsonify({'success': False, 'message': 'Start date is required'}), 400
        
        database_path = 'database'
        assembly_path = os.path.join(database_path, assembly_name)
        
        if not os.path.exists(assembly_path):
            return jsonify({'success': False, 'message': 'Assembly not found'}), 404
        
        # Parse dates
        try:
            start_date_obj = datetime.strptime(start_date, '%Y-%m-%d')
            end_date_obj = None
            if end_date:
                end_date_obj = datetime.strptime(end_date, '%Y-%m-%d')
        except ValueError:
            return jsonify({'success': False, 'message': 'Invalid date format'}), 400
        
        messages = []
        
        # Scan date directories
        try:
            assembly_contents = os.listdir(assembly_path)
            for item in assembly_contents:
                item_path = os.path.join(assembly_path, item)
                if os.path.isdir(item_path):
                    try:
                        date_obj = datetime.strptime(item, '%Y-%m-%d')
                        
                        # Check if date is within range
                        if not end_date_obj:
                            # If no end date, check if date matches start date exactly
                            if date_obj == start_date_obj:
                                messages.extend(scan_messages_directory(item_path, sentiment))
                        else:
                            # If end date provided, check if date is within range (inclusive)
                            if start_date_obj <= date_obj <= end_date_obj:
                                messages.extend(scan_messages_directory(item_path, sentiment))
                                
                    except ValueError:
                        continue
        except Exception as e:
            return jsonify({'success': False, 'message': f'Error reading assembly: {str(e)}'}), 500
        
        # Group messages by group name for better analytics
        groups = {}
        for message in messages:
            # Extract group name from file path
            file_path = message.get('file_path', '')
            if file_path:
                # Extract filename from path and remove .json extension
                filename = os.path.basename(file_path)
                if filename.endswith('.json'):
                    group_name = filename[:-5]  # Remove .json extension
                else:
                    group_name = filename
            else:
                group_name = message.get('group_name', 'Unknown Group')
            
            if group_name not in groups:
                groups[group_name] = {
                    'name': group_name,
                    'count': 0
                }
            groups[group_name]['count'] += 1
        
        return jsonify({
            'success': True,
            'assembly_name': assembly_name,
            'start_date': start_date,
            'end_date': end_date,
            'sentiment': sentiment,
            'total_messages': len(messages),
            'total_groups': len(groups),
            'groups': groups,
            'messages': messages
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500

def scan_messages_directory(date_path, sentiment):
    """Scan messages directory and return message data"""
    messages = []
    messages_dir = os.path.join(date_path, 'messages')
    
    if not os.path.exists(messages_dir):
        return messages
    
    try:
        for filename in os.listdir(messages_dir):
            if filename.endswith('.json'):
                file_path = os.path.join(messages_dir, filename)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        
                        # Filter by sentiment if specified
                        if sentiment != 'all':
                            if isinstance(data, list):
                                # If data is a list of messages
                                for msg in data:
                                    if msg.get('predicted_sentiment', '').lower() == sentiment.lower():
                                        msg['file_path'] = os.path.relpath(file_path, 'database')
                                        messages.append(msg)
                            else:
                                # If data is a single message
                                if data.get('predicted_sentiment', '').lower() == sentiment.lower():
                                    data['file_path'] = os.path.relpath(file_path, 'database')
                                    messages.append(data)
                        else:
                            # Include all messages
                            if isinstance(data, list):
                                for msg in data:
                                    msg['file_path'] = os.path.relpath(file_path, 'database')
                                    messages.append(msg)
                            else:
                                data['file_path'] = os.path.relpath(file_path, 'database')
                                messages.append(data)
                                
                except (json.JSONDecodeError, IOError) as e:
                    print(f"Error reading {file_path}: {e}")
                    continue
                    
    except Exception as e:
        print(f"Error scanning messages directory {messages_dir}: {e}")
    
    return messages

@api_bp.route('/analyze-json-files', methods=['POST'])
@login_required
def analyze_json_files():
    """Analyze JSON files in selected assemblies within date range"""
    try:
        import os
        import traceback
        import json
        
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'No data provided'
            }), 400
        
        assemblies = data.get('assemblies', [])
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        sentiment = data.get('sentiment', 'all')
        
        print(f"Debug: Received data - assemblies: {assemblies}, start_date: {start_date}, end_date: {end_date}, sentiment: {sentiment}")
        
        if not assemblies:
            return jsonify({
                'success': False,
                'message': 'No assemblies selected'
            }), 400
        
        if not start_date:
            return jsonify({
                'success': False,
                'message': 'Start date is required'
            }), 400
        
        # Parse dates
        try:
            start_date_obj = datetime.strptime(start_date, '%Y-%m-%d')
            end_date_obj = None
            if end_date:
                end_date_obj = datetime.strptime(end_date, '%Y-%m-%d')
                if end_date_obj < start_date_obj:
                    return jsonify({
                        'success': False,
                        'message': 'End date must be after start date'
                    }), 400
        except ValueError as ve:
            print(f"Debug: Date parsing error - {ve}")
            return jsonify({
                'success': False,
                'message': f'Invalid date format. Use YYYY-MM-DD. Error: {str(ve)}'
            }), 400
        
        database_path = 'database'
        print(f"Debug: Database path: {database_path}")
        print(f"Debug: Database path exists: {os.path.exists(database_path)}")
        
        results = {
            'total_json_files': 0,
            'assembly_breakdown': [],
            'detailed_results': [],
            'sentiment_breakdown': {
                'Positive': 0,
                'Negative': 0,
                'Neutral': 0
            }
        }
        
        # Check if database directory exists
        if not os.path.exists(database_path):
            print(f"Debug: Database directory does not exist: {database_path}")
            return jsonify({
                'success': True,
                'results': results
            })
        
        # Process each selected assembly
        for assembly_name in assemblies:
            print(f"Debug: Processing assembly: {assembly_name}")
            assembly_path = os.path.join(database_path, assembly_name)
            print(f"Debug: Assembly path: {assembly_path}")
            print(f"Debug: Assembly path exists: {os.path.exists(assembly_path)}")
            
            if not os.path.exists(assembly_path):
                print(f"Debug: Assembly directory does not exist: {assembly_path}")
                continue
            
            # Get all date directories in assembly
            date_dirs = []
            try:
                assembly_contents = os.listdir(assembly_path)
                print(f"Debug: Assembly contents: {assembly_contents}")
                
                for item in assembly_contents:
                    item_path = os.path.join(assembly_path, item)
                    if os.path.isdir(item_path):
                        try:
                            # Try to parse as date
                            date_obj = datetime.strptime(item, '%Y-%m-%d')
                            
                            # Check if date is within range - FIXED LOGIC
                            if not end_date_obj:
                                # If no end date, check if date matches start date exactly
                                if date_obj == start_date_obj:
                                    date_dirs.append((item, date_obj))
                                    print(f"Debug: Added date directory (exact match): {item}")
                            else:
                                # If end date provided, check if date is within range (inclusive)
                                if start_date_obj <= date_obj <= end_date_obj:
                                    date_dirs.append((item, date_obj))
                                    print(f"Debug: Added date directory (range): {item}")
                        except ValueError:
                            # Skip non-date directories
                            print(f"Debug: Skipping non-date directory: {item}")
                            continue
            except Exception as e:
                print(f"Debug: Error reading assembly directory {assembly_path}: {e}")
                continue
            
            # Sort dates
            date_dirs.sort(key=lambda x: x[1])
            print(f"Debug: Sorted date directories: {[d[0] for d in date_dirs]}")
            
            assembly_total = 0
            assembly_sentiment_counts = {'Positive': 0, 'Negative': 0, 'Neutral': 0}
            
            for date_str, date_obj in date_dirs:
                messages_path = os.path.join(assembly_path, date_str, 'messages')
                print(f"Debug: Checking messages path: {messages_path}")
                print(f"Debug: Messages path exists: {os.path.exists(messages_path)}")
                
                if os.path.exists(messages_path):
                    try:
                        # Count JSON files in messages directory
                        messages_contents = os.listdir(messages_path)
                        print(f"Debug: Messages directory contents: {messages_contents}")
                        
                        json_files = [f for f in messages_contents 
                                    if f.lower().endswith('.json')]
                        
                        json_count = len(json_files)
                        print(f"Debug: Found {json_count} JSON files in {messages_path}")
                        
                        assembly_total += json_count
                        results['total_json_files'] += json_count
                        
                        # Analyze sentiment in JSON files
                        for json_file in json_files:
                            try:
                                file_path = os.path.join(messages_path, json_file)
                                with open(file_path, 'r', encoding='utf-8') as f:
                                    data = json.load(f)
                                    
                                    # Process sentiment data
                                    if isinstance(data, list):
                                        for msg in data:
                                            sentiment_value = msg.get('predicted_sentiment', 'Neutral')
                                            if sentiment_value in ['Positive', 'Negative', 'Neutral']:
                                                assembly_sentiment_counts[sentiment_value] += 1
                                                results['sentiment_breakdown'][sentiment_value] += 1
                                    else:
                                        sentiment_value = data.get('predicted_sentiment', 'Neutral')
                                        if sentiment_value in ['Positive', 'Negative', 'Neutral']:
                                            assembly_sentiment_counts[sentiment_value] += 1
                                            results['sentiment_breakdown'][sentiment_value] += 1
                            except Exception as e:
                                print(f"Debug: Error reading sentiment from {json_file}: {e}")
                                continue
                        
                        # Add to detailed results
                        results['detailed_results'].append({
                            'assembly_name': assembly_name,
                            'date': date_str,
                            'json_count': json_count,
                            'json_files': json_files
                        })
                    except Exception as e:
                        print(f"Debug: Error reading messages directory {messages_path}: {e}")
                        continue
                else:
                    print(f"Debug: Messages directory does not exist: {messages_path}")
            
            # Add to assembly breakdown (even if no files found, show the assembly)
            if not end_date_obj:
                date_display = f"Date: {start_date}"
            else:
                date_display = f"Date Range: {start_date} to {end_date}"
            
            breakdown_info = {
                'assembly_name': assembly_name,
                'total_files': assembly_total,
                'date': date_display,
                'json_count': assembly_total,
                'sentiment_counts': assembly_sentiment_counts
            }
            results['assembly_breakdown'].append(breakdown_info)
            
            if assembly_total > 0:
                print(f"Debug: Added assembly breakdown for {assembly_name}: {assembly_total} files")
            else:
                print(f"Debug: No JSON files found for assembly {assembly_name}, but added to breakdown")
        
        print(f"Debug: Final results: {results}")
        return jsonify({
            'success': True,
            'results': results
        })
        
    except Exception as e:
        print(f"Debug: Exception in analyze_json_files: {e}")
        print(f"Debug: Traceback: {traceback.format_exc()}")
        return jsonify({
            'success': False,
            'message': f'Error analyzing JSON files: {str(e)}'
        }), 500

@api_bp.route('/group-sender-analysis', methods=['POST'])
@login_required
def group_sender_analysis():
    """Analyze group sender statistics with detailed breakdown"""
    try:
        data = request.get_json()
        assemblies = data.get('assemblies', [])
        start_date = data.get('startDate')
        end_date = data.get('endDate')
        sentiment_filter = data.get('sentiment', 'all')
        
        if not assemblies:
            return jsonify({
                'success': False,
                'message': 'Please select at least one assembly'
            }), 400
        
        if not start_date:
            return jsonify({
                'success': False,
                'message': 'Start date is required'
            }), 400
        
        results = {
            'total_groups': 0,
            'total_unique_senders': 0,
            'total_messages': 0,
            'group_analysis': []
        }
        
        for assembly_name in assemblies:
            assembly_path = os.path.join('database', assembly_name)
            if not os.path.exists(assembly_path):
                continue
            
            # Get all date directories
            date_dirs = []
            for item in os.listdir(assembly_path):
                item_path = os.path.join(assembly_path, item)
                if os.path.isdir(item_path) and os.path.basename(item_path).count('-') == 2:
                    date_dirs.append(item)
            
            # Filter dates based on start and end date
            if end_date:
                # Date range: include dates between start and end (inclusive)
                filtered_dates = []
                for date_dir in date_dirs:
                    try:
                        date_obj = datetime.strptime(date_dir, '%Y-%m-%d')
                        start_obj = datetime.strptime(start_date, '%Y-%m-%d')
                        end_obj = datetime.strptime(end_date, '%Y-%m-%d')
                        
                        if start_obj <= date_obj <= end_obj:
                            filtered_dates.append(date_dir)
                    except ValueError:
                        continue
            else:
                # Single date: exact match only
                filtered_dates = [start_date] if start_date in date_dirs else []
            
            for date_dir in filtered_dates:
                messages_path = os.path.join(assembly_path, date_dir, 'messages')
                if not os.path.exists(messages_path):
                    continue
                
                # Get all JSON files (groups) in this date directory
                json_files = [f for f in os.listdir(messages_path) if f.endswith('.json')]
                
                for json_file in json_files:
                    group_name = json_file.replace('.json', '')
                    file_path = os.path.join(messages_path, json_file)
                    
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            
                        if isinstance(data, list):
                            # Analyze group messages
                            group_stats = analyze_group_messages(data, sentiment_filter)
                            
                            if group_stats['total_messages'] > 0:
                                results['total_groups'] += 1
                                results['total_messages'] += group_stats['total_messages']
                                results['total_unique_senders'] += group_stats['unique_senders']
                                
                                # Add group analysis
                                group_analysis = {
                                    'assembly': assembly_name,
                                    'date': date_dir,
                                    'group_name': group_name,
                                    'total_messages': group_stats['total_messages'],
                                    'unique_senders': group_stats['unique_senders'],
                                    'top_sender': group_stats['top_sender'],
                                    'sentiment_breakdown': group_stats['sentiment_breakdown'],
                                    'label_breakdown': group_stats['label_breakdown'],
                                    'sender_details': group_stats['sender_details']
                                }
                                
                                results['group_analysis'].append(group_analysis)
                    
                    except Exception as e:
                        print(f"Debug: Error analyzing group {group_name}: {e}")
                        continue
        
        # Sort groups by total messages (highest to lowest)
        results['group_analysis'].sort(key=lambda x: x['total_messages'], reverse=True)
        
        return jsonify({
            'success': True,
            'results': results
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error during group sender analysis: {str(e)}'
        }), 500

@api_bp.route('/common-members-analysis', methods=['POST'])
@login_required
def common_members_analysis():
    """Analyze common members across multiple groups"""
    try:
        data = request.get_json()
        assemblies = data.get('assemblies', [])
        start_date = data.get('startDate')
        end_date = data.get('endDate')
        sentiment_filter = data.get('sentiment', 'all')
        
        if not assemblies:
            return jsonify({
                'success': False,
                'message': 'Please select at least one assembly'
            }), 400
        
        if not start_date:
            return jsonify({
                'success': False,
                'message': 'Start date is required'
            }), 400
        
        # Dictionary to track members across groups
        member_groups = {}  # phone -> {name, groups: [], total_messages: 0, sentiment_counts: {}}
        
        for assembly_name in assemblies:
            assembly_path = os.path.join('database', assembly_name)
            if not os.path.exists(assembly_path):
                continue
            
            # Get all date directories
            date_dirs = []
            for item in os.listdir(assembly_path):
                item_path = os.path.join(assembly_path, item)
                if os.path.isdir(item_path) and os.path.basename(item_path).count('-') == 2:
                    date_dirs.append(item)
            
            # Filter dates based on start and end date
            if end_date:
                # Date range: include dates between start and end (inclusive)
                filtered_dates = []
                for date_dir in date_dirs:
                    try:
                        date_obj = datetime.strptime(date_dir, '%Y-%m-%d')
                        start_obj = datetime.strptime(start_date, '%Y-%m-%d')
                        end_obj = datetime.strptime(end_date, '%Y-%m-%d')
                        
                        if start_obj <= date_obj <= end_obj:
                            filtered_dates.append(date_dir)
                    except ValueError:
                        continue
            else:
                # Single date: exact match only
                filtered_dates = [start_date] if start_date in date_dirs else []
            
            for date_dir in filtered_dates:
                messages_path = os.path.join(assembly_path, date_dir, 'messages')
                if not os.path.exists(messages_path):
                    continue
                
                # Get all JSON files (groups) in this date directory
                json_files = [f for f in os.listdir(messages_path) if f.endswith('.json')]
                
                for json_file in json_files:
                    group_name = json_file.replace('.json', '')
                    file_path = os.path.join(messages_path, json_file)
                    
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            
                        if isinstance(data, list):
                            # Process messages for common members analysis
                            for msg in data:
                                sender = msg.get('sender', {})
                                phone_number = sender.get('phoneNumber', '')
                                sender_name = msg.get('sender', {}).get('name', 'Unknown')
                                
                                if not phone_number:
                                    continue
                                
                                # Apply sentiment filter
                                if sentiment_filter != 'all':
                                    msg_sentiment = msg.get('predicted_sentiment', 'Neutral')
                                    if msg_sentiment.lower() != sentiment_filter.lower():
                                        continue
                                
                                # Initialize member if not exists
                                if phone_number not in member_groups:
                                    member_groups[phone_number] = {
                                        'name': sender_name,
                                        'phone': phone_number,
                                        'groups': [],
                                        'total_messages': 0,
                                        'sentiment_counts': {'Positive': 0, 'Negative': 0, 'Neutral': 0}
                                    }
                                
                                # Add group if not already added
                                group_info = f"{assembly_name}/{date_dir}/{group_name}"
                                if group_info not in member_groups[phone_number]['groups']:
                                    member_groups[phone_number]['groups'].append(group_info)
                                
                                # Count messages
                                member_groups[phone_number]['total_messages'] += 1
                                
                                # Count sentiments
                                sentiment = msg.get('predicted_sentiment', 'Neutral')
                                if sentiment in member_groups[phone_number]['sentiment_counts']:
                                    member_groups[phone_number]['sentiment_counts'][sentiment] += 1
                    
                    except Exception as e:
                        print(f"Debug: Error analyzing group {group_name}: {e}")
                        continue
        
        # Filter members who are in multiple groups (2 or more)
        common_members = []
        for phone, member_data in member_groups.items():
            if len(member_data['groups']) >= 2:  # At least 2 groups
                common_members.append({
                    'name': member_data['name'],
                    'phone': member_data['phone'],
                    'groups_count': len(member_data['groups']),
                    'group_names': member_data['groups'],
                    'total_messages': member_data['total_messages'],
                    'sentiment_breakdown': member_data['sentiment_counts']
                })
        
        # Sort by groups count (highest to lowest), then by total messages
        common_members.sort(key=lambda x: (x['groups_count'], x['total_messages']), reverse=True)
        
        # Calculate summary statistics
        total_common_members = len(common_members)
        max_groups_per_member = max([m['groups_count'] for m in common_members]) if common_members else 0
        total_crossings = sum([m['groups_count'] for m in common_members])
        
        results = {
            'total_common_members': total_common_members,
            'max_groups_per_member': max_groups_per_member,
            'total_crossings': total_crossings,
            'common_members': common_members
        }
        
        return jsonify({
            'success': True,
            'results': results
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error during common members analysis: {str(e)}'
        }), 500

@api_bp.route('/export-common-members-excel', methods=['POST'])
@login_required
def export_common_members_excel():
    """Export common members analysis as Excel file with specific format"""
    try:
        import pandas as pd
        from io import BytesIO
        
        data = request.get_json()
        assemblies = data.get('assemblies', [])
        start_date = data.get('startDate')
        end_date = data.get('endDate')
        sentiment_filter = data.get('sentiment', 'all')
        
        if not assemblies:
            return jsonify({
                'success': False,
                'message': 'Please select at least one assembly'
            }), 400
        
        if not start_date:
            return jsonify({
                'success': False,
                'message': 'Start date is required'
            }), 400
        
        # Dictionary to track members across groups
        member_groups = {}  # phone -> {name, groups: [], total_messages: 0, sentiment_counts: {}}
        
        for assembly_name in assemblies:
            assembly_path = os.path.join('database', assembly_name)
            if not os.path.exists(assembly_path):
                continue
            
            # Get all date directories
            date_dirs = []
            for item in os.listdir(assembly_path):
                item_path = os.path.join(assembly_path, item)
                if os.path.isdir(item_path) and os.path.basename(item_path).count('-') == 2:
                    date_dirs.append(item)
            
            # Filter dates based on start and end date
            if end_date:
                # Date range: include dates between start and end (inclusive)
                filtered_dates = []
                for date_dir in date_dirs:
                    try:
                        date_obj = datetime.strptime(date_dir, '%Y-%m-%d')
                        start_obj = datetime.strptime(start_date, '%Y-%m-%d')
                        end_obj = datetime.strptime(end_date, '%Y-%m-%d')
                        
                        if start_obj <= date_obj <= end_obj:
                            filtered_dates.append(date_dir)
                    except ValueError:
                        continue
            else:
                # Single date: exact match only
                filtered_dates = [start_date] if start_date in date_dirs else []
            
            for date_dir in filtered_dates:
                messages_path = os.path.join(assembly_path, date_dir, 'messages')
                if not os.path.exists(messages_path):
                    continue
                
                # Get all JSON files (groups) in this date directory
                json_files = [f for f in os.listdir(messages_path) if f.endswith('.json')]
                
                for json_file in json_files:
                    group_name = json_file.replace('.json', '')
                    file_path = os.path.join(messages_path, json_file)
                    
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            
                        if isinstance(data, list):
                            # Process messages for common members analysis
                            for msg in data:
                                sender = msg.get('sender', {})
                                phone_number = sender.get('phoneNumber', '')
                                sender_name = msg.get('sender', {}).get('name', 'Unknown')
                                
                                if not phone_number:
                                    continue
                                
                                # Apply sentiment filter
                                if sentiment_filter != 'all':
                                    msg_sentiment = msg.get('predicted_sentiment', 'Neutral')
                                    if msg_sentiment.lower() != sentiment_filter.lower():
                                        continue
                                
                                # Initialize member if not exists
                                if phone_number not in member_groups:
                                    member_groups[phone_number] = {
                                        'name': sender_name,
                                        'phone': phone_number,
                                        'groups': [],
                                        'total_messages': 0,
                                        'sentiment_counts': {'Positive': 0, 'Negative': 0, 'Neutral': 0}
                                    }
                                
                                # Add group if not already added
                                group_info = f"{assembly_name}/{date_dir}/{group_name}"
                                if group_info not in member_groups[phone_number]['groups']:
                                    member_groups[phone_number]['groups'].append(group_info)
                                
                                # Count messages
                                member_groups[phone_number]['total_messages'] += 1
                                
                                # Count sentiments
                                sentiment = msg.get('predicted_sentiment', 'Neutral')
                                if sentiment in member_groups[phone_number]['sentiment_counts']:
                                    member_groups[phone_number]['sentiment_counts'][sentiment] += 1
                    
                    except Exception as e:
                        print(f"Debug: Error analyzing group {group_name}: {e}")
                        continue
        
        # Filter members who are in multiple groups (2 or more)
        common_members = []
        for phone, member_data in member_groups.items():
            if len(member_data['groups']) >= 2:  # At least 2 groups
                common_members.append({
                    'name': member_data['name'],
                    'phone': member_data['phone'],
                    'groups_count': len(member_data['groups']),
                    'group_names': member_data['groups'],
                    'total_messages': member_data['total_messages'],
                    'sentiment_breakdown': member_data['sentiment_counts']
                })
        
        # Sort by groups count (highest to lowest), then by total messages
        common_members.sort(key=lambda x: (x['groups_count'], x['total_messages']), reverse=True)
        
        # Create DataFrame with the exact format requested
        excel_data = []
        for rank, member in enumerate(common_members, 1):
            # Format group names for better readability
            formatted_group_names = []
            for group_info in member['group_names']:
                parts = group_info.split('/')
                if len(parts) >= 3:
                    # Format as "Assembly - Group Name"
                    formatted_group_names.append(f"{parts[0]} - {parts[2]}")
                else:
                    formatted_group_names.append(group_info)
            
            excel_data.append({
                'Rank': rank,
                'Member Name': member['name'],
                'Phone Number': member['phone'],
                'Groups Count': member['groups_count'],
                'Group Names': '; '.join(formatted_group_names)
            })
        
        # Create DataFrame
        df = pd.DataFrame(excel_data)
        
        # Create Excel file in memory
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Common Members', index=False)
            
            # Get the workbook and worksheet
            workbook = writer.book
            worksheet = writer.sheets['Common Members']
            
            # Auto-adjust column widths
            for column in worksheet.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = min(max_length + 2, 50)  # Cap at 50 characters
                worksheet.column_dimensions[column_letter].width = adjusted_width
        
        # Prepare file for download
        output.seek(0)
        
        # Generate filename
        current_date = datetime.now().strftime('%Y-%m-%d')
        filename = f'common_members_analysis_{current_date}.xlsx'
        
        return send_file(
            BytesIO(output.getvalue()),
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error exporting common members Excel: {str(e)}'
        }), 500

@api_bp.route('/export-positive-users-excel', methods=['POST'])
@login_required
def export_positive_users_excel():
    """Export most positive active users from group sender analysis as Excel file"""
    try:
        import pandas as pd
        from io import BytesIO
        
        data = request.get_json()
        assemblies = data.get('assemblies', [])
        start_date = data.get('startDate')
        end_date = data.get('endDate')
        sentiment_filter = data.get('sentiment', 'all')
        
        if not assemblies:
            return jsonify({
                'success': False,
                'message': 'Please select at least one assembly'
            }), 400
        
        if not start_date:
            return jsonify({
                'success': False,
                'message': 'Start date is required'
            }), 400
        
        # Dictionary to track all users across all groups
        all_users = {}  # phone -> {name, phone, total_messages, positive_messages, negative_messages, neutral_messages, groups: []}
        
        for assembly_name in assemblies:
            assembly_path = os.path.join('database', assembly_name)
            if not os.path.exists(assembly_path):
                continue
            
            # Get all date directories
            date_dirs = []
            for item in os.listdir(assembly_path):
                item_path = os.path.join(assembly_path, item)
                if os.path.isdir(item_path) and os.path.basename(item_path).count('-') == 2:
                    date_dirs.append(item)
            
            # Filter dates based on start and end date
            if end_date:
                # Date range: include dates between start and end (inclusive)
                filtered_dates = []
                for date_dir in date_dirs:
                    try:
                        date_obj = datetime.strptime(date_dir, '%Y-%m-%d')
                        start_obj = datetime.strptime(start_date, '%Y-%m-%d')
                        end_obj = datetime.strptime(end_date, '%Y-%m-%d')
                        
                        if start_obj <= date_obj <= end_obj:
                            filtered_dates.append(date_dir)
                    except ValueError:
                        continue
            else:
                # Single date: exact match only
                filtered_dates = [start_date] if start_date in date_dirs else []
            
            for date_dir in filtered_dates:
                messages_path = os.path.join(assembly_path, date_dir, 'messages')
                if not os.path.exists(messages_path):
                    continue
                
                # Get all JSON files (groups) in this date directory
                json_files = [f for f in os.listdir(messages_path) if f.endswith('.json')]
                
                for json_file in json_files:
                    group_name = json_file.replace('.json', '')
                    file_path = os.path.join(messages_path, json_file)
                    
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            
                        if isinstance(data, list):
                            # Process messages for user analysis
                            for msg in data:
                                sender = msg.get('sender', {})
                                phone_number = sender.get('phoneNumber', '')
                                sender_name = msg.get('sender', {}).get('name', 'Unknown')
                                
                                if not phone_number:
                                    continue
                                
                                # Apply sentiment filter
                                if sentiment_filter != 'all':
                                    msg_sentiment = msg.get('predicted_sentiment', 'Neutral')
                                    if msg_sentiment.lower() != sentiment_filter.lower():
                                        continue
                                
                                # Initialize user if not exists
                                if phone_number not in all_users:
                                    all_users[phone_number] = {
                                        'name': sender_name,
                                        'phone': phone_number,
                                        'total_messages': 0,
                                        'positive_messages': 0,
                                        'negative_messages': 0,
                                        'neutral_messages': 0,
                                        'groups': set()
                                    }
                                
                                # Count messages
                                all_users[phone_number]['total_messages'] += 1
                                all_users[phone_number]['groups'].add(f"{assembly_name}/{date_dir}/{group_name}")
                                
                                # Count sentiments
                                sentiment = msg.get('predicted_sentiment', 'Neutral')
                                if sentiment == 'Positive':
                                    all_users[phone_number]['positive_messages'] += 1
                                elif sentiment == 'Negative':
                                    all_users[phone_number]['negative_messages'] += 1
                                elif sentiment == 'Neutral':
                                    all_users[phone_number]['neutral_messages'] += 1
                    
                    except Exception as e:
                        print(f"Debug: Error analyzing group {group_name}: {e}")
                        continue
        
        # Convert to list and filter users with positive messages
        positive_users = []
        for phone, user_data in all_users.items():
            if user_data['positive_messages'] > 0:  # Only include users with positive messages
                positive_users.append({
                    'name': user_data['name'],
                    'phone': user_data['phone'],
                    'total_messages': user_data['total_messages'],
                    'positive_messages': user_data['positive_messages'],
                    'negative_messages': user_data['negative_messages'],
                    'neutral_messages': user_data['neutral_messages'],
                    'groups_count': len(user_data['groups']),
                    'positive_percentage': round((user_data['positive_messages'] / user_data['total_messages']) * 100, 2)
                })
        
        # Sort by positive messages (highest to lowest), then by positive percentage
        positive_users.sort(key=lambda x: (x['positive_messages'], x['positive_percentage']), reverse=True)
        
        # Create DataFrame with the exact format requested
        excel_data = []
        for rank, user in enumerate(positive_users, 1):
            excel_data.append({
                'Rank': rank,
                'Member Name': user['name'],
                'Phone Number': user['phone'],
                'Total Messages': user['total_messages'],
                'Positive Messages': user['positive_messages'],
                'Negative Messages': user['negative_messages'],
                'Neutral Messages': user['neutral_messages'],
                'Groups Count': user['groups_count'],
                'Positive Percentage': f"{user['positive_percentage']}%"
            })
        
        # Create DataFrame
        df = pd.DataFrame(excel_data)
        
        # Create Excel file in memory
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Most Positive Users', index=False)
            
            # Get the workbook and worksheet
            workbook = writer.book
            worksheet = writer.sheets['Most Positive Users']
            
            # Auto-adjust column widths
            for column in worksheet.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = min(max_length + 2, 50)  # Cap at 50 characters
                worksheet.column_dimensions[column_letter].width = adjusted_width
        
        # Prepare file for download
        output.seek(0)
        
        # Generate filename
        current_date = datetime.now().strftime('%Y-%m-%d')
        filename = f'most_positive_users_{current_date}.xlsx'
        
        return send_file(
            BytesIO(output.getvalue()),
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error exporting positive users Excel: {str(e)}'
        }), 500

@api_bp.route('/export-negative-users-excel', methods=['POST'])
@login_required
def export_negative_users_excel():
    """Export most negative active users from group sender analysis as Excel file"""
    try:
        import pandas as pd
        from io import BytesIO
        
        data = request.get_json()
        assemblies = data.get('assemblies', [])
        start_date = data.get('startDate')
        end_date = data.get('endDate')
        sentiment_filter = data.get('sentiment', 'all')
        
        if not assemblies:
            return jsonify({
                'success': False,
                'message': 'Please select at least one assembly'
            }), 400
        
        if not start_date:
            return jsonify({
                'success': False,
                'message': 'Start date is required'
            }), 400
        
        # Dictionary to track all users across all groups
        all_users = {}  # phone -> {name, phone, total_messages, positive_messages, negative_messages, neutral_messages, groups: []}
        
        for assembly_name in assemblies:
            assembly_path = os.path.join('database', assembly_name)
            if not os.path.exists(assembly_path):
                continue
            
            # Get all date directories
            date_dirs = []
            for item in os.listdir(assembly_path):
                item_path = os.path.join(assembly_path, item)
                if os.path.isdir(item_path) and os.path.basename(item_path).count('-') == 2:
                    date_dirs.append(item)
            
            # Filter dates based on start and end date
            if end_date:
                # Date range: include dates between start and end (inclusive)
                filtered_dates = []
                for date_dir in date_dirs:
                    try:
                        date_obj = datetime.strptime(date_dir, '%Y-%m-%d')
                        start_obj = datetime.strptime(start_date, '%Y-%m-%d')
                        end_obj = datetime.strptime(end_date, '%Y-%m-%d')
                        
                        if start_obj <= date_obj <= end_obj:
                            filtered_dates.append(date_dir)
                    except ValueError:
                        continue
            else:
                # Single date: exact match only
                filtered_dates = [start_date] if start_date in date_dirs else []
            
            for date_dir in filtered_dates:
                messages_path = os.path.join(assembly_path, date_dir, 'messages')
                if not os.path.exists(messages_path):
                    continue
                
                # Get all JSON files (groups) in this date directory
                json_files = [f for f in os.listdir(messages_path) if f.endswith('.json')]
                
                for json_file in json_files:
                    group_name = json_file.replace('.json', '')
                    file_path = os.path.join(messages_path, json_file)
                    
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            
                        if isinstance(data, list):
                            # Process messages for user analysis
                            for msg in data:
                                sender = msg.get('sender', {})
                                phone_number = sender.get('phoneNumber', '')
                                sender_name = msg.get('sender', {}).get('name', 'Unknown')
                                
                                if not phone_number:
                                    continue
                                
                                # Apply sentiment filter
                                if sentiment_filter != 'all':
                                    msg_sentiment = msg.get('predicted_sentiment', 'Neutral')
                                    if msg_sentiment.lower() != sentiment_filter.lower():
                                        continue
                                
                                # Initialize user if not exists
                                if phone_number not in all_users:
                                    all_users[phone_number] = {
                                        'name': sender_name,
                                        'phone': phone_number,
                                        'total_messages': 0,
                                        'positive_messages': 0,
                                        'negative_messages': 0,
                                        'neutral_messages': 0,
                                        'groups': set()
                                    }
                                
                                # Count messages
                                all_users[phone_number]['total_messages'] += 1
                                all_users[phone_number]['groups'].add(f"{assembly_name}/{date_dir}/{group_name}")
                                
                                # Count sentiments
                                sentiment = msg.get('predicted_sentiment', 'Neutral')
                                if sentiment == 'Positive':
                                    all_users[phone_number]['positive_messages'] += 1
                                elif sentiment == 'Negative':
                                    all_users[phone_number]['negative_messages'] += 1
                                elif sentiment == 'Neutral':
                                    all_users[phone_number]['neutral_messages'] += 1
                    
                    except Exception as e:
                        print(f"Debug: Error analyzing group {group_name}: {e}")
                        continue
        
        # Convert to list and filter users with negative messages
        negative_users = []
        for phone, user_data in all_users.items():
            if user_data['negative_messages'] > 0:  # Only include users with negative messages
                negative_users.append({
                    'name': user_data['name'],
                    'phone': user_data['phone'],
                    'total_messages': user_data['total_messages'],
                    'positive_messages': user_data['positive_messages'],
                    'negative_messages': user_data['negative_messages'],
                    'neutral_messages': user_data['neutral_messages'],
                    'groups_count': len(user_data['groups']),
                    'negative_percentage': round((user_data['negative_messages'] / user_data['total_messages']) * 100, 2)
                })
        
        # Sort by negative messages (highest to lowest), then by negative percentage
        negative_users.sort(key=lambda x: (x['negative_messages'], x['negative_percentage']), reverse=True)
        
        # Create DataFrame with the exact format requested
        excel_data = []
        for rank, user in enumerate(negative_users, 1):
            excel_data.append({
                'Rank': rank,
                'Member Name': user['name'],
                'Phone Number': user['phone'],
                'Total Messages': user['total_messages'],
                'Positive Messages': user['positive_messages'],
                'Negative Messages': user['negative_messages'],
                'Neutral Messages': user['neutral_messages'],
                'Groups Count': user['groups_count'],
                'Negative Percentage': f"{user['negative_percentage']}%"
            })
        
        # Create DataFrame
        df = pd.DataFrame(excel_data)
        
        # Create Excel file in memory
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Most Negative Users', index=False)
            
            # Get the workbook and worksheet
            workbook = writer.book
            worksheet = writer.sheets['Most Negative Users']
            
            # Auto-adjust column widths
            for column in worksheet.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = min(max_length + 2, 50)  # Cap at 50 characters
                worksheet.column_dimensions[column_letter].width = adjusted_width
        
        # Prepare file for download
        output.seek(0)
        
        # Generate filename
        current_date = datetime.now().strftime('%Y-%m-%d')
        filename = f'most_negative_users_{current_date}.xlsx'
        
        return send_file(
            BytesIO(output.getvalue()),
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error exporting negative users Excel: {str(e)}'
        }), 500

def analyze_group_messages(messages_data, sentiment_filter):
    """Helper function to analyze messages within a group"""
    sender_stats = {}
    sentiment_counts = {'Positive': 0, 'Negative': 0, 'Neutral': 0}
    label_counts = {}
    
    for msg in messages_data:
        # Get sender info
        sender = msg.get('sender', {})
        phone_number = sender.get('phoneNumber', '')
        sender_name = sender.get('name', 'Unknown')
        
        if not phone_number:
            continue
        
        # Apply sentiment filter
        if sentiment_filter != 'all':
            msg_sentiment = msg.get('predicted_sentiment', 'Neutral')
            if msg_sentiment.lower() != sentiment_filter.lower():
                continue
        
        # Count messages per sender
        if phone_number not in sender_stats:
            sender_stats[phone_number] = {
                'name': sender_name,
                'phone': phone_number,
                'message_count': 0,
                'messages': []
            }
        
        sender_stats[phone_number]['message_count'] += 1
        
        # Add message details
        message_info = {
            'content': msg.get('messageContent', ''),
            'type': msg.get('messageType', 'text'),
            'timestamp': msg.get('timestamp', ''),
            'sentiment': msg.get('predicted_sentiment', 'Neutral'),
            'label': msg.get('predicted_label', 'unknown')
        }
        sender_stats[phone_number]['messages'].append(message_info)
        
        # Count sentiments
        sentiment = msg.get('predicted_sentiment', 'Neutral')
        if sentiment in sentiment_counts:
            sentiment_counts[sentiment] += 1
        
        # Count labels
        label = msg.get('predicted_label', 'unknown')
        label_counts[label] = label_counts.get(label, 0) + 1
    
    # Find top sender
    top_sender = None
    if sender_stats:
        top_sender = max(sender_stats.values(), key=lambda x: x['message_count'])
        top_sender = {
            'name': top_sender['name'],
            'phone': top_sender['phone'],
            'message_count': top_sender['message_count']
        }
    
    return {
        'total_messages': len(messages_data),
        'unique_senders': len(sender_stats),
        'sender_details': list(sender_stats.values()),
        'sentiment_breakdown': sentiment_counts,
        'label_breakdown': label_counts,
        'top_sender': top_sender
    }

# ============================================================================
# GROUP DETAILS API
# ============================================================================

@api_bp.route('/group-details', methods=['POST'])
@login_required
def get_group_details():
    """Get detailed group information with messages separated by sentiment"""
    try:
        data = request.get_json()
        group_name = data.get('groupName')
        assembly = data.get('assembly')
        date = data.get('date')

        if not group_name or not assembly or not date:
            return jsonify({
                'success': False,
                'message': 'Group name, assembly, and date are required'
            }), 400

        # Construct file path
        file_path = os.path.join('database', assembly, date, 'messages', f'{group_name}.json')
        
        if not os.path.exists(file_path):
            return jsonify({
                'success': False,
                'message': 'Group file not found'
            }), 404

        # Read and process the JSON file
        with open(file_path, 'r', encoding='utf-8') as f:
            messages_data = json.load(f)

        if not isinstance(messages_data, list):
            return jsonify({
                'success': False,
                'message': 'Invalid message data format'
            }), 400

        # Process messages and collect statistics
        total_messages = len(messages_data)
        unique_senders = {}
        sentiment_counts = {'Positive': 0, 'Negative': 0, 'Neutral': 0}
        messages_by_sentiment = {'Positive': [], 'Negative': [], 'Neutral': []}

        for message in messages_data:
            sender = message.get('sender', {})
            sender_name = sender.get('name', 'Unknown')
            sender_phone = sender.get('phoneNumber', 'Unknown')
            sentiment = message.get('predicted_sentiment', 'Neutral')
            label = message.get('predicted_label', 'unknown')
            timestamp = message.get('timestamp', '')
            content = message.get('messageContent', '')

            # Count sentiment
            if sentiment in sentiment_counts:
                sentiment_counts[sentiment] += 1

            # Collect unique senders
            if sender_phone not in unique_senders:
                unique_senders[sender_phone] = {
                    'name': sender_name,
                    'phone': sender_phone,
                    'message_count': 0,
                    'sentiment_breakdown': {'Positive': 0, 'Negative': 0, 'Neutral': 0}
                }

            unique_senders[sender_phone]['message_count'] += 1
            if sentiment in unique_senders[sender_phone]['sentiment_breakdown']:
                unique_senders[sender_phone]['sentiment_breakdown'][sentiment] += 1

            # Add message to sentiment categories
            message_obj = {
                'content': content,
                'sender_name': sender_name,
                'sender_phone': sender_phone,
                'timestamp': timestamp,
                'label': label,
                'sentiment': sentiment
            }

            if sentiment in messages_by_sentiment:
                messages_by_sentiment[sentiment].append(message_obj)

        # Find top sender
        top_sender = None
        if unique_senders:
            top_sender_phone = max(unique_senders.keys(), key=lambda x: unique_senders[x]['message_count'])
            top_sender_data = unique_senders[top_sender_phone]
            top_sender = {
                'name': top_sender_data['name'],
                'phone': top_sender_data['phone'],
                'message_count': top_sender_data['message_count'],
                'percentage': round((top_sender_data['message_count'] / total_messages) * 100, 1)
            }

        # Convert unique senders to list and sort by message count
        unique_senders_list = list(unique_senders.values())
        unique_senders_list.sort(key=lambda x: x['message_count'], reverse=True)

        # Group info
        group_info = {
            'total_messages': total_messages,
            'unique_senders': len(unique_senders),
            'sentiment_counts': sentiment_counts
        }

        results = {
            'group_info': group_info,
            'top_sender': top_sender,
            'unique_senders': unique_senders_list,
            'messages_by_sentiment': messages_by_sentiment
        }

        return jsonify({
            'success': True,
            'results': results
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error getting group details: {str(e)}'
        }), 500

# ============================================================================
# MEMBER DETAILS API
# ============================================================================

@api_bp.route('/member-details/<phone>', methods=['POST'])
@login_required
def get_member_details(phone):
    """Get detailed member information with all messages separated by sentiment"""
    try:
        data = request.get_json()
        assemblies = data.get('assemblies', [])
        start_date = data.get('startDate')
        end_date = data.get('endDate')
        
        if not assemblies:
            return jsonify({
                'success': False,
                'message': 'Please select at least one assembly'
            }), 400
        
        if not start_date:
            return jsonify({
                'success': False,
                'message': 'Start date is required'
            }), 400
        
        # Dictionary to store messages by sentiment
        messages_by_sentiment = {
            'Positive': [],
            'Negative': [],
            'Neutral': []
        }
        
        member_info = {
            'name': 'Unknown',
            'phone': phone,
            'total_messages': 0,
            'groups_involved': set(),
            'sentiment_counts': {'Positive': 0, 'Negative': 0, 'Neutral': 0}
        }
        
        for assembly_name in assemblies:
            assembly_path = os.path.join('database', assembly_name)
            if not os.path.exists(assembly_path):
                continue
            
            # Get all date directories
            date_dirs = []
            for item in os.listdir(assembly_path):
                item_path = os.path.join(assembly_path, item)
                if os.path.isdir(item_path) and os.path.basename(item_path).count('-') == 2:
                    date_dirs.append(item)
            
            # Filter dates based on start and end date
            if end_date:
                # Date range: include dates between start and end (inclusive)
                filtered_dates = []
                for date_dir in date_dirs:
                    try:
                        date_obj = datetime.strptime(date_dir, '%Y-%m-%d')
                        start_obj = datetime.strptime(start_date, '%Y-%m-%d')
                        end_obj = datetime.strptime(end_date, '%Y-%m-%d')
                        
                        if start_obj <= date_obj <= end_obj:
                            filtered_dates.append(date_dir)
                    except ValueError:
                        continue
            else:
                # Single date: exact match only
                filtered_dates = [start_date] if start_date in date_dirs else []
            
            for date_dir in filtered_dates:
                messages_path = os.path.join(assembly_path, date_dir, 'messages')
                if not os.path.exists(messages_path):
                    continue
                
                # Get all JSON files (groups) in this date directory
                json_files = [f for f in os.listdir(messages_path) if f.endswith('.json')]
                
                for json_file in json_files:
                    group_name = json_file.replace('.json', '')
                    file_path = os.path.join(messages_path, json_file)
                    
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            
                        if isinstance(data, list):
                            # Process messages for this specific member
                            for msg in data:
                                sender = msg.get('sender', {})
                                msg_phone = sender.get('phoneNumber', '')
                                
                                if msg_phone == phone:
                                    # Update member info
                                    if member_info['name'] == 'Unknown':
                                        member_info['name'] = msg.get('sender', {}).get('name', 'Unknown')
                                    
                                    member_info['total_messages'] += 1
                                    member_info['groups_involved'].add(f"{assembly_name}/{date_dir}/{group_name}")
                                    
                                    # Get sentiment
                                    sentiment = msg.get('predicted_sentiment', 'Neutral')
                                    if sentiment in member_info['sentiment_counts']:
                                        member_info['sentiment_counts'][sentiment] += 1
                                    
                                    # Create message object
                                    message_obj = {
                                        'content': msg.get('messageContent', ''),
                                        'type': msg.get('messageType', 'text'),
                                        'timestamp': msg.get('timestamp', ''),
                                        'sentiment': sentiment,
                                        'label': msg.get('predicted_label', 'unknown'),
                                        'group_name': group_name,
                                        'assembly': assembly_name,
                                        'date': date_dir
                                    }
                                    
                                    # Add to appropriate sentiment category
                                    if sentiment in messages_by_sentiment:
                                        messages_by_sentiment[sentiment].append(message_obj)
                    
                    except Exception as e:
                        print(f"Debug: Error processing group {group_name}: {e}")
                        continue
        
        # Convert groups_involved set to list
        member_info['groups_involved'] = list(member_info['groups_involved'])
        
        # Sort messages by timestamp within each sentiment category
        for sentiment in messages_by_sentiment:
            messages_by_sentiment[sentiment].sort(
                key=lambda x: x.get('timestamp', ''), 
                reverse=True
            )
        
        results = {
            'member_info': member_info,
            'messages_by_sentiment': messages_by_sentiment
        }
        
        return jsonify({
            'success': True,
            'results': results
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error getting member details: {str(e)}'
        }), 500

# ============================================================================
# MESSAGE SEARCH API
# ============================================================================

@api_bp.route('/search-messages', methods=['POST'])
@login_required
def search_messages():
    """Search messages across all groups and assemblies"""
    try:
        data = request.get_json()
        search_term = data.get('searchTerm', '').strip().lower()
        search_field = data.get('searchField', 'messageContent')  # Default to message content
        assemblies = data.get('assemblies', [])
        start_date = data.get('startDate', '')
        end_date = data.get('endDate', '')
        selected_label = data.get('label', 'all')
        selected_sentiment = data.get('sentiment', 'all')
        
        if not search_term:
            return jsonify({
                'success': False,
                'message': 'Search term is required'
            }), 400
        
        if not assemblies:
            return jsonify({
                'success': False,
                'message': 'At least one assembly must be selected'
            }), 400
        
        if not start_date:
            return jsonify({
                'success': False,
                'message': 'Start date is required'
            }), 400
        
        search_results = []
        total_messages = 0
        total_members = set()
        total_groups = set()
        
        # Search through each assembly
        for assembly_name in assemblies:
            assembly_path = os.path.join('database', assembly_name)
            if not os.path.exists(assembly_path):
                continue
            
            # Get date directories
            try:
                date_dirs = [d for d in os.listdir(assembly_path) 
                           if os.path.isdir(os.path.join(assembly_path, d)) and 
                           d.replace('-', '').isdigit()]
            except:
                continue
            
            # Filter dates based on start and end date
            if end_date:
                # Date range: include dates between start and end (inclusive)
                filtered_dates = []
                for date_dir in date_dirs:
                    try:
                        date_obj = datetime.strptime(date_dir, '%Y-%m-%d')
                        start_obj = datetime.strptime(start_date, '%Y-%m-%d')
                        end_obj = datetime.strptime(end_date, '%Y-%m-%d')
                        
                        if start_obj <= date_obj <= end_obj:
                            filtered_dates.append(date_dir)
                    except ValueError:
                        continue
            else:
                # Single date: exact match only
                filtered_dates = [start_date] if start_date in date_dirs else []
            
            # Search through each date directory
            for date_dir in filtered_dates:
                messages_path = os.path.join(assembly_path, date_dir, 'messages')
                if not os.path.exists(messages_path):
                    continue
                
                # Get all JSON files (groups) in this date directory
                json_files = [f for f in os.listdir(messages_path) if f.endswith('.json')]
                
                for json_file in json_files:
                    group_name = json_file.replace('.json', '')
                    file_path = os.path.join(messages_path, json_file)
                    
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            
                        if isinstance(data, list):
                            # Search through messages in this group
                            for msg in data:
                                message_content = msg.get('messageContent', '').lower()
                                sender = msg.get('sender', {})
                                sender_name = sender.get('name', 'Unknown')
                                sender_phone = sender.get('phoneNumber', '')
                                sentiment = msg.get('predicted_sentiment', 'Neutral')
                                label = msg.get('predicted_label', 'unknown')
                                timestamp = msg.get('timestamp', '')
                                
                                # Check if message matches search criteria based on search field
                                message_matches = False
                                if search_field == 'messageContent':
                                    message_matches = search_term in message_content
                                elif search_field == 'senderName':
                                    message_matches = search_term in sender_name.lower()
                                elif search_field == 'senderPhone':
                                    message_matches = search_term in sender_phone
                                elif search_field == 'groupName':
                                    message_matches = search_term in group_name.lower()
                                elif search_field == 'assembly':
                                    message_matches = search_term in assembly_name.lower()
                                elif search_field == 'all':
                                    # Search in all fields
                                    message_matches = (
                                        search_term in message_content or
                                        search_term in sender_name.lower() or
                                        search_term in sender_phone or
                                        search_term in group_name.lower() or
                                        search_term in assembly_name.lower()
                                    )
                                else:
                                    # Default to message content
                                    message_matches = search_term in message_content
                                
                                label_matches = selected_label == 'all' or label == selected_label
                                sentiment_matches = selected_sentiment == 'all' or sentiment.lower() == selected_sentiment
                                
                                if message_matches and label_matches and sentiment_matches:
                                    # Add to search results
                                    search_result = {
                                        'message_content': msg.get('messageContent', ''),
                                        'sender_name': sender_name,
                                        'sender_phone': sender_phone,
                                        'sentiment': sentiment,
                                        'label': label,
                                        'timestamp': timestamp,
                                        'group_name': group_name,
                                        'assembly': assembly_name,
                                        'date': date_dir
                                    }
                                    
                                    search_results.append(search_result)
                                    total_members.add(sender_phone)
                                    total_groups.add(f"{assembly_name}/{date_dir}/{group_name}")
                                    total_messages += 1
                    
                    except Exception as e:
                        print(f"Debug: Error searching in group {group_name}: {e}")
                        continue
        
        # Sort results by timestamp (newest first)
        search_results.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        
        results = {
            'search_results': search_results,
            'total_messages': total_messages,
            'total_members': len(total_members),
            'total_groups': len(total_groups),
            'search_term': search_term
        }
        
        return jsonify({
            'success': True,
            'results': results
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error searching messages: {str(e)}'
        }), 500

# ============================================================================
# ASSEMBLY GROUPS API
# ============================================================================

@api_bp.route('/assembly-groups', methods=['POST'])
@login_required
def get_assembly_groups():
    """Get WhatsApp groups for a specific assembly with phone number counts"""
    try:
        data = request.get_json()
        print(f"Debug: Received data: {data}")
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'No JSON data received'
            }), 400
        
        assembly_name = data.get('assembly_name', '').strip()
        print(f"Debug: Assembly name: '{assembly_name}'")
        
        if not assembly_name:
            return jsonify({
                'success': False,
                'message': 'Assembly name is required'
            }), 400
        
        # Define the database path for the assembly
        database_path = 'database'
        assembly_path = os.path.join(database_path, assembly_name)
        
        if not os.path.exists(assembly_path):
            return jsonify({
                'success': False,
                'message': f'Assembly "{assembly_name}" not found'
            }), 404
        
        groups = []
        total_phones = 0
        total_members = 0
        
        # Look for groups in the groups subdirectory
        groups_path = os.path.join(assembly_path, 'groups')
        if os.path.exists(groups_path):
            # Get all CSV files in the groups directory
            csv_files = [f for f in os.listdir(groups_path) if f.endswith('.csv')]
            
            for csv_file in csv_files:
                try:
                    # Extract group name from filename (remove _all_timestamp.csv)
                    group_name = csv_file.replace('_all_', '_').split('_')[0]
                    print(f"Debug: Processing CSV file '{csv_file}' -> group_name: '{group_name}'")
                    
                    # Skip files that result in empty group names
                    if not group_name or group_name.strip() == '':
                        print(f"Debug: Skipping file '{csv_file}' - empty group name")
                        continue
                    
                    # Get file info
                    file_path = os.path.join(groups_path, csv_file)
                    file_stat = os.stat(file_path)
                    file_size = file_stat.st_size
                    last_modified = datetime.fromtimestamp(file_stat.st_mtime)
                    
                    # For now, we'll estimate phone numbers based on file size
                    # In a real implementation, you'd read the CSV file to count actual phone numbers
                    estimated_phones = estimate_phone_count_from_file(file_path)
                    
                    groups.append({
                        'group_name': group_name,
                        'assembly': assembly_name,
                        'phone_count': estimated_phones,
                        'member_count': estimated_phones,  # Assuming 1 phone = 1 member for now
                        'file_size': file_size,
                        'last_updated': last_modified.isoformat(),
                        'filename': csv_file
                    })
                    
                    total_phones += estimated_phones
                    total_members += estimated_phones
                    
                except Exception as e:
                    print(f"Debug: Error processing group file {csv_file}: {e}")
                    continue
        
        # Sort groups by phone count (highest to lowest)
        groups.sort(key=lambda x: x.get('phone_count', 0), reverse=True)
        
        summary = {
            'total_groups': len(groups),
            'total_phones': total_phones,
            'total_members': total_members
        }
        
        return jsonify({
            'success': True,
            'groups': groups,
            'summary': summary
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error getting assembly groups: {str(e)}'
        }), 500

@api_bp.route('/download-group-excel', methods=['GET'])
@login_required
def download_group_excel():
    """Download Excel file with phone numbers for a specific group"""
    try:
        group_name = request.args.get('group', '').strip()
        assembly_name = request.args.get('assembly', '').strip()
        filename = request.args.get('filename', '').strip()
        
        print(f"Debug: Download request - Group: {group_name}, Assembly: {assembly_name}, Filename: {filename}")
        
        if not group_name or not assembly_name:
            return jsonify({
                'success': False,
                'message': 'Group name and assembly are required'
            }), 400
        
        # Define the database path for the assembly
        database_path = 'database'
        assembly_path = os.path.join(database_path, assembly_name)
        
        if not os.path.exists(assembly_path):
            return jsonify({
                'success': False,
                'message': f'Assembly "{assembly_name}" not found'
            }), 404
        
        # Look for the CSV file in the groups subdirectory
        groups_path = os.path.join(assembly_path, 'groups')
        if not os.path.exists(groups_path):
            return jsonify({
                'success': False,
                'message': f'Groups directory not found for assembly "{assembly_name}"'
            }), 404
        
        # Find the CSV file
        csv_file_path = None
        if filename and filename.endswith('.csv'):
            # Use the provided filename
            csv_file_path = os.path.join(groups_path, filename)
        else:
            # Search for CSV files that match the group name
            csv_files = [f for f in os.listdir(groups_path) if f.endswith('.csv')]
            for csv_file in csv_files:
                if group_name.lower() in csv_file.lower():
                    csv_file_path = os.path.join(groups_path, csv_file)
                    break
        
        if not csv_file_path or not os.path.exists(csv_file_path):
            return jsonify({
                'success': False,
                'message': f'CSV file not found for group "{group_name}"'
            }), 404
        
        print(f"Debug: Found CSV file: {csv_file_path}")
        
        # Read the CSV file and convert to Excel
        try:
            import pandas as pd
            
            # Read CSV file with different encodings
            try:
                df = pd.read_csv(csv_file_path, encoding='utf-8')
            except UnicodeDecodeError:
                try:
                    df = pd.read_csv(csv_file_path, encoding='latin-1')
                except:
                    df = pd.read_csv(csv_file_path, encoding='cp1252')
            
            # Create Excel file in memory
            from io import BytesIO
            excel_buffer = BytesIO()
            
            # Write to Excel with phone numbers sheet
            with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Phone Numbers', index=False)
            
            excel_buffer.seek(0)
            
            # Generate filename
            safe_group_name = "".join(c for c in group_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
            excel_filename = f"{safe_group_name}_phone_numbers.xlsx"
            
            print(f"Debug: Generated Excel file: {excel_filename}")
            
            # Return Excel file
            return send_file(
                excel_buffer,
                as_attachment=True,
                download_name=excel_filename,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            
        except Exception as e:
            print(f"Debug: Error processing CSV file: {e}")
            return jsonify({
                'success': False,
                'message': f'Error processing CSV file: {str(e)}'
            }), 500
        
    except Exception as e:
        print(f"Debug: Error in download_group_excel: {e}")
        return jsonify({
            'success': False,
            'message': f'Error downloading group Excel: {str(e)}'
        }), 500

@api_bp.route('/download-all-phone-numbers', methods=['GET'])
@login_required
def download_all_phone_numbers():
    """Download Excel file with all phone numbers from all groups in an assembly"""
    try:
        assembly_name = request.args.get('assembly', '').strip()
        
        print(f"Debug: Download all phone numbers request - Assembly: {assembly_name}")
        
        if not assembly_name:
            return jsonify({
                'success': False,
                'message': 'Assembly name is required'
            }), 400
        
        # Define the database path for the assembly
        database_path = 'database'
        assembly_path = os.path.join(database_path, assembly_name)
        
        if not os.path.exists(assembly_path):
            return jsonify({
                'success': False,
                'message': f'Assembly "{assembly_name}" not found'
            }), 404
        
        # Look for CSV files in the groups subdirectory
        groups_path = os.path.join(assembly_path, 'groups')
        if not os.path.exists(groups_path):
            return jsonify({
                'success': False,
                'message': f'Groups directory not found for assembly "{assembly_name}"'
            }), 404
        
        # Get all CSV files
        csv_files = [f for f in os.listdir(groups_path) if f.endswith('.csv')]
        
        if not csv_files:
            return jsonify({
                'success': False,
                'message': f'No CSV files found in assembly "{assembly_name}"'
            }), 404
        
        print(f"Debug: Found {len(csv_files)} CSV files")
        
        try:
            import pandas as pd
            from io import BytesIO
            
            # Create Excel file in memory
            excel_buffer = BytesIO()
            
            with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                all_phone_numbers = []
                group_summary = []
                
                for csv_file in csv_files:
                    try:
                        csv_file_path = os.path.join(groups_path, csv_file)
                        
                        # Extract group name from filename
                        group_name = csv_file.replace('_all_', '_').split('_')[0]
                        
                        # Read CSV file with different encodings
                        try:
                            df = pd.read_csv(csv_file_path, encoding='utf-8')
                        except UnicodeDecodeError:
                            try:
                                df = pd.read_csv(csv_file_path, encoding='latin-1')
                            except:
                                df = pd.read_csv(csv_file_path, encoding='cp1252')
                        
                        # Look for phone number columns
                        phone_columns = []
                        for col in df.columns:
                            col_lower = str(col).lower()
                            if any(keyword in col_lower for keyword in ['phone', 'number', 'mobile', 'contact', 'whatsapp']):
                                phone_columns.append(col)
                        
                        if phone_columns:
                            # Get phone numbers from the first phone column
                            phone_col = phone_columns[0]
                            phone_numbers = df[phone_col].dropna().unique()
                            
                            # Add to all phone numbers list
                            for phone in phone_numbers:
                                all_phone_numbers.append({
                                    'Group Name': group_name,
                                    'Phone Number': phone,
                                    'Assembly': assembly_name
                                })
                            
                            # Add to group summary
                            group_summary.append({
                                'Group Name': group_name,
                                'Phone Count': len(phone_numbers),
                                'Assembly': assembly_name
                            })
                            
                            print(f"Debug: Processed {group_name} - {len(phone_numbers)} phone numbers")
                        
                    except Exception as e:
                        print(f"Debug: Error processing {csv_file}: {e}")
                        continue
                
                # Create summary sheet
                if group_summary:
                    summary_df = pd.DataFrame(group_summary)
                    summary_df.to_excel(writer, sheet_name='Group Summary', index=False)
                
                # Create all phone numbers sheet
                if all_phone_numbers:
                    all_phones_df = pd.DataFrame(all_phone_numbers)
                    all_phones_df.to_excel(writer, sheet_name='All Phone Numbers', index=False)
                
                # Create unique phone numbers sheet (deduplicated)
                if all_phone_numbers:
                    unique_phones = []
                    seen_phones = set()
                    
                    for phone_data in all_phone_numbers:
                        phone = phone_data['Phone Number']
                        if phone not in seen_phones:
                            seen_phones.add(phone)
                            unique_phones.append({
                                'Phone Number': phone,
                                'Assembly': assembly_name
                            })
                    
                    if unique_phones:
                        unique_df = pd.DataFrame(unique_phones)
                        unique_df.to_excel(writer, sheet_name='Unique Phone Numbers', index=False)
            
            excel_buffer.seek(0)
            
            # Generate filename
            safe_assembly_name = "".join(c for c in assembly_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
            excel_filename = f"{safe_assembly_name}_all_phone_numbers.xlsx"
            
            print(f"Debug: Generated Excel file: {excel_filename}")
            print(f"Debug: Total phone numbers: {len(all_phone_numbers)}")
            print(f"Debug: Unique phone numbers: {len(unique_phones) if 'unique_phones' in locals() else 0}")
            
            # Return Excel file
            return send_file(
                excel_buffer,
                as_attachment=True,
                download_name=excel_filename,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            
        except Exception as e:
            print(f"Debug: Error processing CSV files: {e}")
            return jsonify({
                'success': False,
                'message': f'Error processing CSV files: {str(e)}'
            }), 500
        
    except Exception as e:
        print(f"Debug: Error in download_all_phone_numbers: {e}")
        return jsonify({
            'success': False,
            'message': f'Error downloading all phone numbers: {str(e)}'
        }), 500

def estimate_phone_count_from_file(file_path):
    """Estimate phone number count from CSV file based on file size and structure"""
    try:
        # Try to read the CSV file to get actual phone number count
        try:
            import pandas as pd
            
            # Read CSV file with different encodings
            try:
                df = pd.read_csv(file_path, encoding='utf-8')
            except UnicodeDecodeError:
                try:
                    df = pd.read_csv(file_path, encoding='latin-1')
                except:
                    df = pd.read_csv(file_path, encoding='cp1252')
            
            # Look for phone number columns (common names)
            phone_columns = []
            for col in df.columns:
                col_lower = str(col).lower()
                if any(keyword in col_lower for keyword in ['phone', 'number', 'mobile', 'contact', 'whatsapp']):
                    phone_columns.append(col)
            
            if phone_columns:
                # Count unique phone numbers in the first phone column found
                phone_col = phone_columns[0]
                phone_count = df[phone_col].dropna().nunique()
                print(f"Debug: Found {phone_count} unique phone numbers in column '{phone_col}'")
                return max(1, phone_count)
            else:
                # If no phone columns found, estimate from file size
                file_size = os.path.getsize(file_path)
                estimated_phones = max(1, file_size // 200)  # More conservative estimate
                estimated_phones = min(estimated_phones, 5000)
                print(f"Debug: No phone columns found, estimated {estimated_phones} from file size")
                return estimated_phones
                
        except ImportError:
            # pandas not available, fall back to file size estimation
            print("Debug: pandas not available, using file size estimation")
            file_size = os.path.getsize(file_path)
            estimated_phones = max(1, file_size // 200)
            estimated_phones = min(estimated_phones, 5000)
            return estimated_phones
            
        except Exception as e:
            # Error reading CSV file, fall back to file size estimation
            print(f"Debug: Error reading CSV file {file_path}: {e}")
            file_size = os.path.getsize(file_path)
            estimated_phones = max(1, file_size // 200)
            estimated_phones = min(estimated_phones, 5000)
            return estimated_phones
        
    except Exception as e:
        print(f"Debug: Error in estimate_phone_count_from_file for {file_path}: {e}")
        return 100  # Default fallback

# ============================================================================
# LABEL MANAGEMENT API
# ============================================================================

@api_bp.route('/get-labels', methods=['GET'])
@login_required
def get_labels():
    """Get available labels from CSV file"""
    try:
        import csv
        import os
        
        labels = []
        csv_file = 'label.csv'
        
        if os.path.exists(csv_file):
            with open(csv_file, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    labels.append({
                        'name': row['label_name'],
                        'color': row['label_color'],
                        'description': row['label_description']
                    })
        
        return jsonify({
            'success': True,
            'labels': labels
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error loading labels: {str(e)}'
        }), 500

@api_bp.route('/save-labels', methods=['POST'])
@login_required
def save_labels():
    """Save labels to CSV file"""
    try:
        import csv
        import os
        
        data = request.get_json()
        labels = data.get('labels', [])
        
        csv_file = 'label.csv'
        
        with open(csv_file, 'w', newline='', encoding='utf-8') as file:
            fieldnames = ['label_name', 'label_color', 'label_description']
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            
            writer.writeheader()
            for label in labels:
                writer.writerow({
                    'label_name': label['name'],
                    'label_color': label['color'],
                    'label_description': label['description']
                })
        
        return jsonify({
            'success': True,
            'message': 'Labels saved successfully'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error saving labels: {str(e)}'
        }), 500

@api_bp.route('/get-group-labels', methods=['POST'])
@login_required
def get_group_labels():
    """Get labels for a specific group"""
    try:
        data = request.get_json()
        print(f"Debug: get-group-labels received data: {data}")
        
        if not data:
            print("Debug: No JSON data received")
            return jsonify({
                'success': False,
                'message': 'No JSON data received'
            }), 400
        
        assembly_name = data.get('assembly_name')
        group_name = data.get('group_name')
        
        print(f"Debug: assembly_name='{assembly_name}', group_name='{group_name}'")
        
        if not assembly_name or not group_name:
            print(f"Debug: Missing required fields - assembly_name: {bool(assembly_name)}, group_name: {bool(group_name)}")
            return jsonify({
                'success': False,
                'message': 'Assembly name and group name are required'
            }), 400
        
        # Load group labels from JSON file
        labels_file = os.path.join('database', assembly_name, 'group_labels.json')
        group_labels = {}
        
        if os.path.exists(labels_file):
            try:
                with open(labels_file, 'r', encoding='utf-8') as file:
                    group_labels = json.load(file)
            except json.JSONDecodeError as e:
                print(f"Debug: JSON decode error in {labels_file}: {e}")
                # If JSON is corrupted, return empty list
                group_labels = {}
        
        labels = group_labels.get(group_name, [])
        
        return jsonify({
            'success': True,
            'labels': labels
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error getting group labels: {str(e)}'
        }), 500

@api_bp.route('/get-all-group-labels', methods=['POST'])
@login_required
def get_all_group_labels():
    """Get labels for all groups in an assembly at once"""
    try:
        data = request.get_json()
        print(f"Debug: get-all-group-labels received data: {data}")
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'No JSON data received'
            }), 400
        
        assembly_name = data.get('assembly_name')
        
        if not assembly_name:
            return jsonify({
                'success': False,
                'message': 'Assembly name is required'
            }), 400
        
        # Load group labels from JSON file
        labels_file = os.path.join('database', assembly_name, 'group_labels.json')
        group_labels = {}
        
        if os.path.exists(labels_file):
            try:
                with open(labels_file, 'r', encoding='utf-8') as file:
                    group_labels = json.load(file)
            except json.JSONDecodeError as e:
                print(f"Debug: JSON decode error in {labels_file}: {e}")
                # If JSON is corrupted, return empty dict
                group_labels = {}
        
        return jsonify({
            'success': True,
            'group_labels': group_labels
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error getting all group labels: {str(e)}'
        }), 500

@api_bp.route('/save-group-labels', methods=['POST'])
@login_required
def save_group_labels():
    """Save labels for a specific group"""
    try:
        data = request.get_json()
        assembly_name = data.get('assembly_name')
        group_name = data.get('group_name')
        labels = data.get('labels', [])
        
        if not assembly_name or not group_name:
            return jsonify({
                'success': False,
                'message': 'Assembly name and group name are required'
            }), 400
        
        # Ensure directory exists
        assembly_dir = os.path.join('database', assembly_name)
        os.makedirs(assembly_dir, exist_ok=True)
        
        # Load existing labels
        labels_file = os.path.join(assembly_dir, 'group_labels.json')
        group_labels = {}
        
        if os.path.exists(labels_file):
            try:
                with open(labels_file, 'r', encoding='utf-8') as file:
                    group_labels = json.load(file)
            except json.JSONDecodeError as e:
                print(f"Debug: JSON decode error in {labels_file}: {e}")
                # If JSON is corrupted, start with empty dict
                group_labels = {}
        
        # Update labels for this group
        group_labels[group_name] = labels
        
        # Save back to file
        with open(labels_file, 'w', encoding='utf-8') as file:
            json.dump(group_labels, file, indent=2, ensure_ascii=False)
        
        return jsonify({
            'success': True,
            'message': 'Group labels saved successfully'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error saving group labels: {str(e)}'
        }), 500

# ============================================================================
# EMAIL TEST API
# ============================================================================

@api_bp.route('/test-email', methods=['POST'])
@login_required
@admin_required
def test_email():
    """Test email functionality"""
    try:
        from utils.email import send_test_email
        
        # Send test email to the specified address
        success = send_test_email("rahulverma9466105@gmail.com")
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Test email sent successfully!'
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Failed to send test email'
            }), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error sending test email: {str(e)}'
        }), 500

@api_bp.route('/send-welcome-email', methods=['POST'])
@login_required
@admin_required
def send_welcome_email_api():
    """Send welcome email to a user"""
    try:
        data = request.get_json()
        email = data.get('email')
        username = data.get('username')
        
        if not email or not username:
            return jsonify({
                'success': False,
                'message': 'Email and username are required'
            }), 400
        
        from utils.email import send_welcome_email
        
        success = send_welcome_email(email, username)
        
        if success:
            return jsonify({
                'success': True,
                'message': f'Welcome email sent successfully to {email}'
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Failed to send welcome email'
            }), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error sending welcome email: {str(e)}'
        }), 500

# ============================================================================
# SEARCH RESULTS EXPORT API
# ============================================================================

@api_bp.route('/export-search-results', methods=['POST'])
@login_required
def export_search_results():
    """Export search results to Excel file"""
    try:
        import pandas as pd
        import io
        from datetime import datetime
        
        data = request.get_json()
        results = data.get('results', [])
        format_type = data.get('format', 'excel')
        
        if not results:
            return jsonify({
                'success': False,
                'message': 'No results to export'
            }), 400
        
        # Convert results to DataFrame
        df = pd.DataFrame(results)
        
        # Create Excel file in memory
        output = io.BytesIO()
        
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # Write main results sheet
            df.to_excel(writer, sheet_name='Search Results', index=False)
            
            # Add summary sheet
            summary_data = {
                'Metric': ['Total Messages', 'Total Groups', 'Total Assemblies', 'Export Date'],
                'Value': [
                    len(results),
                    len(df['group_name'].unique()) if 'group_name' in df.columns else 0,
                    len(df['assembly'].unique()) if 'assembly' in df.columns else 0,
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                ]
            }
            summary_df = pd.DataFrame(summary_data)
            summary_df.to_excel(writer, sheet_name='Summary', index=False)
            
            # Add unique senders sheet if data exists
            if 'sender_name' in df.columns and 'sender_phone' in df.columns:
                unique_senders = df[['sender_name', 'sender_phone', 'assembly', 'group_name']].drop_duplicates()
                unique_senders.to_excel(writer, sheet_name='Unique Senders', index=False)
        
        output.seek(0)
        
        # Generate filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'search_results_{timestamp}.xlsx'
        
        return send_file(
            output,
            as_attachment=True,
            download_name=filename,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        
    except ImportError:
        return jsonify({
            'success': False,
            'message': 'Excel export requires pandas and openpyxl libraries'
        }), 500
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error exporting search results: {str(e)}'
        }), 500


