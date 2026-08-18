// Admin Message Management JavaScript
let allPosts = [];
let currentFilters = {
    status: '',
    assembly: '',
    date: ''
};
let selectedPostId = null;

// Initialize when page loads
document.addEventListener('DOMContentLoaded', function() {
    loadAllPosts();
    loadStats();
    loadAssemblies();
});

// Load all scheduled posts
async function loadAllPosts() {
    try {
        const response = await fetch('/api/admin/all-scheduled-posts');
        const data = await response.json();
        
        if (data.success) {
            allPosts = data.posts;
            displayAllPosts(data.posts);
            updatePagination(data.pagination);
        } else {
            showError('Failed to load posts: ' + data.message);
        }
    } catch (error) {
        showError('Error loading posts: ' + error.message);
    }
}

// Display all posts in table format
function displayAllPosts(posts) {
    const container = document.getElementById('allPostsTable');
    
    if (posts.length === 0) {
        container.innerHTML = '<p class="no-data">No scheduled posts found.</p>';
        return;
    }
    
    let html = `
        <div class="posts-table">
            <table>
                <thead>
                    <tr>
                        <th>Title</th>
                        <th>User</th>
                        <th>Assembly</th>
                        <th>Scheduled Date/Time</th>
                        <th>Excel Files</th>
                        <th>Content & Files</th>
                        <th>Status</th>
                        <th>Created</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
    `;
    
    posts.forEach(post => {
        const scheduledDateTime = new Date(post.scheduled_date + 'T' + post.scheduled_time);
        
        // Get content types and create download buttons
        const contentTypes = [];
        let downloadButtons = '';
        
        if (post.image_file) {
            contentTypes.push('Image');
            downloadButtons += `<button class="btn btn-sm btn-outline-primary" onclick="downloadFile(${post.id}, 'image')">
                <i class="fas fa-download"></i> Image
            </button>`;
        }
        if (post.audio_file) {
            contentTypes.push('Audio');
            downloadButtons += `<button class="btn btn-sm btn-outline-success" onclick="downloadFile(${post.id}, 'audio')">
                <i class="fas fa-download"></i> Audio
            </button>`;
        }
        if (post.video_file) {
            contentTypes.push('Video');
            downloadButtons += `<button class="btn btn-sm btn-outline-warning" onclick="downloadFile(${post.id}, 'video')">
                <i class="fas fa-download"></i> Video
            </button>`;
        }
        
        const contentText = contentTypes.length > 0 ? contentTypes.join(', ') : 'Text Only';
        
        html += `
            <tr class="post-row status-${post.status}" data-post-id="${post.id}">
                <td class="title-cell">${post.title}</td>
                <td class="user-cell">
                    <div class="user-info">
                        <span class="username">${post.created_by_username || 'User'}</span>
                        <span class="email">${post.created_by_email || ''}</span>
                    </div>
                </td>
                <td class="assembly-cell">${post.assembly_name || 'N/A'}</td>
                <td class="date-cell">${formatDateTime(scheduledDateTime)}</td>
                <td class="files-cell">
                    <div class="files-summary" title="${getFilesTooltip(post.target_groups)}">
                        <i class="fas fa-users"></i>
                        <span class="files-count">${Array.isArray(post.target_groups) ? post.target_groups.length : 0}</span>
                    </div>
                </td>
                <td class="content-cell">
                    <div class="content-info">
                        <span class="content-type">${contentText}</span>
                        ${downloadButtons ? `<div class="download-buttons">${downloadButtons}</div>` : ''}
                    </div>
                </td>
                <td class="status-cell">
                    ${formatStatusBadge(post.status)}
                    ${getTaskCountdownHtml(post) ? `<div style="margin-top: 4px;">${getTaskCountdownHtml(post)}</div>` : ''}
                </td>
                <td class="created-cell">${formatDate(post.created_at)}</td>
                <td class="actions-cell">
                    <button class="btn btn-sm btn-secondary" onclick="viewPostDetails(${post.id})">
                        <i class="fas fa-eye"></i>
                    </button>
                    <button class="btn btn-sm btn-primary" onclick="openStatusUpdate(${post.id})">
                        <i class="fas fa-edit"></i> Status
                    </button>
                    <button class="btn btn-sm btn-danger" onclick="confirmDeletePost(${post.id}, '${post.title}')" title="Delete Post">
                        <i class="fas fa-trash"></i>
                    </button>
                </td>
            </tr>
        `;
    });
    
    html += `
                </tbody>
            </table>
        </div>
    `;
    
    container.innerHTML = html;
}

// Load statistics
async function loadStats() {
    try {
        const response = await fetch('/api/admin/scheduled-posts-stats');
        const data = await response.json();
        
        if (data.success) {
            updateStats(data.stats);
        }
    } catch (error) {
        console.error('Error loading stats:', error);
    }
}

// Update statistics display
function updateStats(stats) {
    document.getElementById('pendingCount').textContent = stats.pending;
    document.getElementById('runningCount').textContent = stats.running;
    document.getElementById('completedCount').textContent = stats.completed;
    document.getElementById('failedCount').textContent = stats.failed;
}

// Load assemblies for filter
async function loadAssemblies() {
    try {
        const response = await fetch('/api/assemblies');
        const data = await response.json();
        
        if (data.success) {
            const assemblySelect = document.getElementById('assemblyFilter');
            data.assemblies.forEach(assembly => {
                const option = document.createElement('option');
                option.value = assembly.name;
                option.textContent = assembly.name;
                assemblySelect.appendChild(option);
            });
        }
    } catch (error) {
        console.error('Error loading assemblies:', error);
    }
}

// Filter posts
function filterPosts() {
    const statusFilter = document.getElementById('statusFilter').value;
    const assemblyFilter = document.getElementById('assemblyFilter').value;
    const dateFilter = document.getElementById('dateFilter').value;
    
    currentFilters = {
        status: statusFilter,
        assembly: assemblyFilter,
        date: dateFilter
    };
    
    // Apply filters to loaded posts
    let filteredPosts = allPosts;
    
    if (statusFilter) {
        filteredPosts = filteredPosts.filter(post => post.status === statusFilter);
    }
    
    if (assemblyFilter) {
        filteredPosts = filteredPosts.filter(post => post.assembly_name === assemblyFilter);
    }
    
    if (dateFilter) {
        filteredPosts = filteredPosts.filter(post => post.scheduled_date === dateFilter);
    }
    
    displayAllPosts(filteredPosts);
}

// Clear all filters
function clearFilters() {
    document.getElementById('statusFilter').value = '';
    document.getElementById('assemblyFilter').value = '';
    document.getElementById('dateFilter').value = '';
    
    currentFilters = {
        status: '',
        assembly: '',
        date: ''
    };
    
    displayAllPosts(allPosts);
}

// View post details
function viewPostDetails(postId) {
    const post = allPosts.find(p => p.id === postId);
    if (!post) return;
    
    const modal = document.getElementById('postDetailsModal');
    const content = document.getElementById('postDetailsContent');
    
    const scheduledDateTime = new Date(post.scheduled_date + 'T' + post.scheduled_time);
    
    // Create download buttons for files
    let fileDownloads = '';
    if (post.image_file) {
        fileDownloads += `<button class="btn btn-outline-primary" onclick="downloadFile(${post.id}, 'image')">
            <i class="fas fa-download"></i> Download Image
        </button>`;
    }
    if (post.audio_file) {
        fileDownloads += `<button class="btn btn-outline-success" onclick="downloadFile(${post.id}, 'audio')">
            <i class="fas fa-download"></i> Download Audio
        </button>`;
    }
    if (post.video_file) {
        fileDownloads += `<button class="btn btn-outline-warning" onclick="downloadFile(${post.id}, 'video')">
            <i class="fas fa-download"></i> Download Video
        </button>`;
    }
    
    // Get target groups count and sample names
    const totalGroups = post.target_groups ? post.target_groups.length : 0;
    let groupsDisplay = '';
    
    if (totalGroups > 0) {
        // Show first 3 groups as examples, then total count
        const sampleGroups = post.target_groups.slice(0, 3);
        const remainingCount = totalGroups - 3;
        
        groupsDisplay = `<p><strong>Total Excel Files:</strong> ${totalGroups}</p>`;
        groupsDisplay += '<p><strong>Sample Files:</strong></p>';
        groupsDisplay += '<ul>';
        sampleGroups.forEach(group => {
            groupsDisplay += `<li>${group.group_name}</li>`;
        });
        groupsDisplay += '</ul>';
        
        if (remainingCount > 0) {
            groupsDisplay += `<p><em>... and ${remainingCount} more files</em></p>`;
        }
    } else {
        groupsDisplay = '<p>No target groups specified</p>';
    }
    
    let detailsHtml = `
        <div class="post-details-grid">
            <div class="detail-section">
                <h4>Basic Information</h4>
                <p><strong>Title:</strong> ${post.title}</p>
                <p><strong>Status:</strong> <span class="status-badge ${post.status}">${post.status.toUpperCase()}</span></p>
                <p><strong>Created By:</strong> ${post.created_by_username} (${post.created_by_email})</p>
                <p><strong>Created At:</strong> ${formatDateTime(new Date(post.created_at))}</p>
            </div>
            
            <div class="detail-section">
                <h4>Scheduling</h4>
                <p><strong>Scheduled Date:</strong> ${formatDate(post.scheduled_date)}</p>
                <p><strong>Scheduled Time:</strong> ${formatTime(post.scheduled_time)}</p>
                <p><strong>Assembly:</strong> ${post.assembly_name || 'N/A'}</p>
            </div>
            
            <div class="detail-section">
                <h4>Content</h4>
                ${post.message_text ? `<p><strong>Message:</strong> ${post.message_text}</p>` : '<p><strong>Message:</strong> No message text</p>'}
                <div class="file-downloads">
                    <h5>Uploaded Files:</h5>
                    ${fileDownloads || '<p>No files uploaded</p>'}
                </div>
                ${post.completion_file ? `
                <div class="completion-file-download">
                    <h5>Completion File:</h5>
                    <button class="btn btn-outline-success" onclick="downloadCompletionFile(${post.id})">
                        <i class="fas fa-download"></i> Download Completion File
                    </button>
                </div>
                ` : ''}
            </div>
            
            <div class="detail-section">
                <h4>Target Groups</h4>
                ${groupsDisplay}
            </div>
        </div>
    `;
    
    content.innerHTML = detailsHtml;
    openModal('postDetailsModal');
}

// Open status update modal
function openStatusUpdate(postId) {
    selectedPostId = postId;
    const post = allPosts.find(p => p.id === postId);
    
    if (post) {
        // Set current status in dropdown
        document.getElementById('newStatus').value = post.status;
        
        // Clear previous notes and file
        document.getElementById('adminNotes').value = '';
        document.getElementById('completionFile').value = '';
        
        // Show/hide completion file field based on current status
        const completionFileGroup = document.getElementById('completionFileGroup');
        if (post.status === 'completed') {
            completionFileGroup.style.display = 'block';
        } else {
            completionFileGroup.style.display = 'none';
        }
        
        // Add event listener to show/hide completion file field when status changes
        document.getElementById('newStatus').onchange = function() {
            if (this.value === 'completed') {
                completionFileGroup.style.display = 'block';
            } else {
                completionFileGroup.style.display = 'none';
            }
        };
        
        // Update modal title to show current status
        const modalTitle = document.querySelector('#statusUpdateModal .modal-header h3');
        if (modalTitle) {
            modalTitle.innerHTML = `<i class="fas fa-edit"></i> Update Status: ${post.title || 'Broadcast'}`;
        }
        
        openModal('statusUpdateModal');
    } else {
        showError('Post not found');
    }
}

// Update post status
async function updatePostStatus() {
    if (!selectedPostId) {
        showError('No post selected for status update');
        return;
    }
    
    const newStatus = document.getElementById('newStatus').value.trim();
    const adminNotes = document.getElementById('adminNotes').value.trim();
    const completionFile = document.getElementById('completionFile').files[0];
    
    // Validation
    if (!newStatus) {
        showError('Please select a new status');
        return;
    }
    
    // Confirm status change
    const post = allPosts.find(p => p.id === selectedPostId);
    if (post && post.status === newStatus) {
        if (!confirm('The selected status is the same as the current status. Do you want to continue?')) {
            return;
        }
    }
    
    try {
        // Show loading state
        const updateBtn = document.querySelector('#statusUpdateModal .btn-success');
        if (updateBtn) {
            updateBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Updating...';
            updateBtn.disabled = true;
        }
        
        // Create FormData for file upload
        const formData = new FormData();
        formData.append('status', newStatus);
        formData.append('admin_notes', adminNotes);
        if (completionFile) {
            formData.append('completion_file', completionFile);
        }
        
        const response = await fetch(`/api/scheduled-posts/${selectedPostId}/status`, {
            method: 'PUT',
            body: formData
        });
        
        const data = await response.json();
        
        if (data.success) {
            showSuccess(`Post status updated to ${newStatus.toUpperCase()}`);
            closeModal('statusUpdateModal');
            
            // Update the post in local array
            if (post) {
                post.status = newStatus;
                post.updated_at = new Date().toISOString();
            }
            
            // Refresh the specific row in the table
            refreshPostRow(selectedPostId);
            
            // Reload statistics
            loadStats();
            
            // Reset form
            document.getElementById('adminNotes').value = '';
            selectedPostId = null;
        } else {
            showError('Failed to update status: ' + data.message);
        }
    } catch (error) {
        showError('Error updating status: ' + error.message);
    } finally {
        // Reset button state
        const updateBtn = document.querySelector('#statusUpdateModal .btn-success');
        if (updateBtn) {
            updateBtn.innerHTML = '<i class="fas fa-check"></i> Update Status';
            updateBtn.disabled = false;
        }
    }
}

// Quick status update function
async function quickStatusUpdate(postId, newStatus) {
    if (!confirm(`Are you sure you want to mark this post as ${newStatus.toUpperCase()}?`)) {
        return;
    }
    
    try {
        const response = await fetch(`/api/scheduled-posts/${postId}/status`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ 
                status: newStatus,
                admin_notes: `Quick status update to ${newStatus}`
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showSuccess(`Post status updated to ${newStatus.toUpperCase()}`);
            
            // Update the post in local array
            const post = allPosts.find(p => p.id === postId);
            if (post) {
                post.status = newStatus;
                post.updated_at = new Date().toISOString();
            }
            
            // Refresh the specific row in the table
            refreshPostRow(postId);
            
            // Reload statistics
            loadStats();
        } else {
            showError('Failed to update status: ' + data.message);
        }
    } catch (error) {
        showError('Error updating status: ' + error.message);
    }
}

// Update pagination display
function updatePagination(pagination) {
    // This can be expanded to show pagination controls
    console.log('Pagination:', pagination);
}

// Format Status Badge
function formatStatusBadge(status) {
    const s = (status || 'pending').toLowerCase();
    if (s === 'running') {
        return `<span class="status-badge running" title="3 Hours Execution Window Active"><i class="fas fa-bolt"></i> RUNNING (3 Hours)</span>`;
    } else if (s === 'completed') {
        return `<span class="status-badge completed"><i class="fas fa-check-circle"></i> COMPLETED</span>`;
    } else if (s === 'failed') {
        return `<span class="status-badge failed"><i class="fas fa-exclamation-circle"></i> FAILED</span>`;
    } else if (s === 'cancelled') {
        return `<span class="status-badge cancelled"><i class="fas fa-ban"></i> CANCELLED</span>`;
    }
    return `<span class="status-badge pending"><i class="fas fa-hourglass-half"></i> PENDING</span>`;
}

// Utility functions
function formatDateTime(dateTime) {
    return dateTime.toLocaleDateString() + ' ' + dateTime.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
}

function formatDate(dateString) {
    return new Date(dateString).toLocaleDateString();
}

function formatTime(timeString) {
    return timeString;
}

// Show success message
function showSuccess(message) {
    alert('Success: ' + message);
}

// Show error message
function showError(message) {
    alert('Error: ' + message);
}

// Open modal
function openModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) modal.style.display = 'flex';
}

// Close modal
function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) modal.style.display = 'none';
}

// Close modal when clicking outside overlay
window.onclick = function(event) {
    const overlays = document.querySelectorAll('.modal-overlay');
    overlays.forEach(overlay => {
        if (event.target === overlay) {
            overlay.style.display = 'none';
        }
    });
}

// Download file function
async function downloadFile(postId, fileType) {
    try {
        const response = await fetch(`/api/admin/download-file/${postId}/${fileType}`);
        
        if (response.ok) {
            // Create a blob from the response
            const blob = await response.blob();
            
            // Create download link
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `${fileType}_post_${postId}.${getFileExtension(fileType)}`;
            document.body.appendChild(a);
            a.click();
            
            // Cleanup
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
            
            showSuccess(`${fileType} file downloaded successfully`);
        } else {
            const data = await response.json();
            showError(`Download failed: ${data.message}`);
            
            // If it's a file not found error, show debug info
            if (data.message && data.message.includes('File not found')) {
                console.log('File not found error. Use the Debug button to troubleshoot file paths.');
            }
        }
    } catch (error) {
        showError('Error downloading file: ' + error.message);
    }
}

// Download completion file function
async function downloadCompletionFile(postId) {
    try {
        const response = await fetch(`/api/download-completion-file/${postId}`);
        
        if (response.ok) {
            // Create a blob from the response
            const blob = await response.blob();
            
            // Create download link
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `completion_file_post_${postId}.xlsx`;
            document.body.appendChild(a);
            a.click();
            
            // Cleanup
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
            
            showSuccess('Completion file downloaded successfully');
        } else {
            const data = await response.json();
            showError(`Download failed: ${data.message}`);
        }
    } catch (error) {
        showError('Error downloading completion file: ' + error.message);
    }
}

// Debug file paths function
async function debugFilePaths(postId) {
    try {
        const response = await fetch(`/api/admin/debug-file-paths/${postId}`);
        const data = await response.json();
        
        if (data.success) {
            const debugInfo = data.debug_info;
            let debugMessage = `Debug Info for Post ${postId}:\n\n`;
            debugMessage += `Assembly: ${debugInfo.assembly_name}\n\n`;
            
            debugMessage += 'Stored Paths:\n';
            Object.entries(debugInfo.stored_paths).forEach(([type, path]) => {
                debugMessage += `${type}: ${path || 'None'}\n`;
            });
            
            debugMessage += '\nConstructed Paths:\n';
            Object.entries(debugInfo.constructed_paths).forEach(([type, path]) => {
                debugMessage += `${type}: ${path || 'None'}\n`;
            });
            
            debugMessage += '\nFile Exists:\n';
            Object.entries(debugInfo.file_exists).forEach(([type, exists]) => {
                debugMessage += `${type}: ${exists ? 'Yes' : 'No'}\n`;
            });
            
            alert(debugMessage);
        } else {
            showError('Debug failed: ' + data.message);
        }
    } catch (error) {
        showError('Error debugging: ' + error.message);
    }
}

// Get file extension based on file type
function getFileExtension(fileType) {
    switch(fileType) {
        case 'image': return 'jpg';
        case 'audio': return 'mp3';
        case 'video': return 'mp4';
        default: return 'file';
    }
}

// Helper function to get tooltip text for target groups
function getFilesTooltip(groups) {
    if (!groups || groups.length === 0) {
        return 'No target groups specified';
    }

    const sampleGroups = groups.slice(0, 3);
    const remainingCount = groups.length - 3;

    let tooltipText = `Total Excel Files: ${groups.length}\n`;
    tooltipText += 'Sample Files:\n';
    sampleGroups.forEach(group => {
        tooltipText += `${group.group_name}\n`;
    });

    if (remainingCount > 0) {
        tooltipText += `... and ${remainingCount} more files`;
    }
    return tooltipText;
}

// Refresh specific post row after status update
function refreshPostRow(postId) {
    const post = allPosts.find(p => p.id === postId);
    if (!post) return;
    
    // Find the row in the table
    const row = document.querySelector(`tr[data-post-id="${postId}"]`);
    if (row) {
        // Update status badge
        const statusCell = row.querySelector('.status-cell .status-badge');
        if (statusCell) {
            statusCell.className = `status-badge ${post.status}`;
            statusCell.textContent = post.status.toUpperCase();
        }
        
        // Update row status class
        row.className = `post-row status-${post.status}`;
    }
}

// Delete post functionality
let postToDelete = null;

function confirmDeletePost(postId, postTitle) {
    postToDelete = postId;
    document.getElementById('deletePostTitle').textContent = postTitle;
    openModal('deleteConfirmModal');
}

async function deletePost() {
    if (!postToDelete) {
        showError('No post selected for deletion');
        return;
    }
    
    try {
        // Show loading state
        const deleteBtn = document.querySelector('#deleteConfirmModal .btn-danger');
        if (deleteBtn) {
            deleteBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Deleting...';
            deleteBtn.disabled = true;
        }
        
        console.log(`Attempting to delete post ID: ${postToDelete}`);
        
        const response = await fetch(`/api/scheduled-posts/${postToDelete}/delete`, {
            method: 'DELETE',
            headers: {
                'Content-Type': 'application/json',
            }
        });
        
        console.log(`Delete response status: ${response.status}`);
        
        const data = await response.json();
        console.log('Delete response data:', data);
        
        if (data.success) {
            showSuccess('Post deleted successfully');
            closeModal('deleteConfirmModal');
            
            // Remove the post from local array
            allPosts = allPosts.filter(p => p.id !== postToDelete);
            
            // Remove the row from the table
            const row = document.querySelector(`tr[data-post-id="${postToDelete}"]`);
            if (row) {
                row.remove();
            }
            
            // Reload statistics
            loadStats();
            
            // Reset
            postToDelete = null;
        } else {
            showError('Failed to delete post: ' + data.message);
            console.error('Delete failed:', data);
        }
    } catch (error) {
        showError('Error deleting post: ' + error.message);
        console.error('Delete error:', error);
    } finally {
        // Reset button state
        const deleteBtn = document.querySelector('#deleteConfirmModal .btn-danger');
        if (deleteBtn) {
            deleteBtn.innerHTML = '<i class="fas fa-trash"></i> Delete Post';
            deleteBtn.disabled = false;
        }
    }
}

// Countdown timer helper for admin panel
function getTaskCountdownHtml(post) {
    const status = (post.status || 'pending').toLowerCase();
    
    if (status === 'running') {
        let startTime = new Date();
        if (post.updated_at) {
            startTime = new Date(post.updated_at);
        } else if (post.scheduled_date && post.scheduled_time) {
            startTime = new Date(post.scheduled_date + 'T' + post.scheduled_time);
        }
        
        const endTime = new Date(startTime.getTime() + (3 * 60 * 60 * 1000)); // +3 Hours Window
        const now = new Date();
        const diffMs = endTime - now;
        
        if (diffMs > 0) {
            const hours = Math.floor(diffMs / (1000 * 60 * 60));
            const mins = Math.floor((diffMs % (1000 * 60 * 60)) / (1000 * 60));
            const secs = Math.floor((diffMs % (1000 * 60)) / 1000);
            const pad = n => String(n).padStart(2, '0');
            return `<span class="timer-countdown-badge running-timer" data-end-time="${endTime.getTime()}"><i class="fas fa-hourglass-half fa-spin"></i> 3h Window: ${pad(hours)}h ${pad(mins)}m ${pad(secs)}s left</span>`;
        } else {
            return `<span class="timer-countdown-badge running-timer"><i class="fas fa-bolt"></i> Running (3h Window)</span>`;
        }
    } else if (status === 'pending') {
        if (post.scheduled_date) {
            const timeStr = post.scheduled_time || '00:00';
            const scheduledTarget = new Date(post.scheduled_date + 'T' + timeStr);
            const now = new Date();
            const diffMs = scheduledTarget - now;
            
            if (diffMs > 0) {
                const hours = Math.floor(diffMs / (1000 * 60 * 60));
                const mins = Math.floor((diffMs % (1000 * 60 * 60)) / (1000 * 60));
                const secs = Math.floor((diffMs % (1000 * 60)) / 1000);
                const pad = n => String(n).padStart(2, '0');
                return `<span class="timer-countdown-badge pending-timer" data-target-time="${scheduledTarget.getTime()}"><i class="fas fa-clock"></i> Starts in ${pad(hours)}h ${pad(mins)}m ${pad(secs)}s</span>`;
            } else {
                return `<span class="timer-countdown-badge pending-timer past"><i class="fas fa-history"></i> Scheduled time reached</span>`;
            }
        }
    }
    return '';
}

// Automatic 1-second interval loop for live timers on admin panel
setInterval(function updateAdminLiveTimers() {
    const pad = n => String(n).padStart(2, '0');
    const now = new Date().getTime();

    document.querySelectorAll('.running-timer[data-end-time]').forEach(elem => {
        const endTime = parseInt(elem.getAttribute('data-end-time'), 10);
        const diffMs = endTime - now;
        if (diffMs > 0) {
            const hours = Math.floor(diffMs / (1000 * 60 * 60));
            const mins = Math.floor((diffMs % (1000 * 60 * 60)) / (1000 * 60));
            const secs = Math.floor((diffMs % (1000 * 60)) / 1000);
            elem.innerHTML = `<i class="fas fa-hourglass-half fa-spin"></i> 3h Window: ${pad(hours)}h ${pad(mins)}m ${pad(secs)}s left`;
        } else {
            elem.innerHTML = `<i class="fas fa-bolt"></i> Running (3h Window)`;
        }
    });

    document.querySelectorAll('.pending-timer[data-target-time]').forEach(elem => {
        const targetTime = parseInt(elem.getAttribute('data-target-time'), 10);
        const diffMs = targetTime - now;
        if (diffMs > 0) {
            const hours = Math.floor(diffMs / (1000 * 60 * 60));
            const mins = Math.floor((diffMs % (1000 * 60 * 60)) / (1000 * 60));
            const secs = Math.floor((diffMs % (1000 * 60)) / 1000);
            elem.innerHTML = `<i class="fas fa-clock"></i> Starts in ${pad(hours)}h ${pad(mins)}m ${pad(secs)}s`;
        } else {
            elem.innerHTML = `<i class="fas fa-history"></i> Scheduled time reached`;
        }
    });
}, 1000);
