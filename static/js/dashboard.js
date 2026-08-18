// Main JavaScript file for WhatsApp UI Dashboard

document.addEventListener('DOMContentLoaded', function() {
    // Initialize all dashboard components
    initializeSidebar();
    initializeCharts();
    initializeFilters();
    initializeActions();
    initializeNotifications();
});

// Sidebar functionality
function initializeSidebar() {
    const menuItems = document.querySelectorAll('.nav-link, .menu-item');
    const sidebar = document.querySelector('.modern-sidebar, .sidebar');
    const mobileToggle = document.querySelector('.mobile-menu-toggle, .hamburger-btn, .mobile-toggle');
    
    if (!sidebar) return;
    
    // Close sidebar when clicking outside on mobile
    document.addEventListener('click', function(e) {
        if (window.innerWidth <= 992) {
            if (sidebar.classList.contains('show') || sidebar.classList.contains('open')) {
                const isClickInsideSidebar = sidebar.contains(e.target);
                const isClickOnToggle = mobileToggle && mobileToggle.contains(e.target);
                
                if (!isClickInsideSidebar && !isClickOnToggle) {
                    if (typeof window.closeMobileMenu === 'function') {
                        window.closeMobileMenu();
                    } else {
                        sidebar.classList.remove('show');
                        sidebar.classList.remove('open');
                    }
                }
            }
        }
    });
}

// Handle menu navigation
function handleMenuNavigation(page) {
    console.log('Navigating to:', page);
}

// Initialize charts (placeholder for future chart implementation)
function initializeCharts() {
    console.log('Charts initialized');
}

// Initialize filters
function initializeFilters() {
    const filterForms = document.querySelectorAll('.search-filter-section form');
    
    filterForms.forEach(form => {
        const resetBtn = form.querySelector('.filter-btn.reset');
        const applyBtn = form.querySelector('.filter-btn.apply');
        
        if (resetBtn) {
            resetBtn.addEventListener('click', function(e) {
                e.preventDefault();
                resetFilters(form);
            });
        }
        
        if (applyBtn) {
            applyBtn.addEventListener('click', function(e) {
                e.preventDefault();
                applyFilters(form);
            });
        }
    });
}

// Reset all filters
function resetFilters(form) {
    const inputs = form.querySelectorAll('input, select');
    inputs.forEach(input => {
        if (input.type === 'date') {
            input.value = '';
        } else if (input.tagName === 'SELECT') {
            input.selectedIndex = 0;
        } else {
            input.value = '';
        }
    });
    showNotification('Filters reset successfully', 'success');
}

// Apply filters
function applyFilters(form) {
    const formData = new FormData(form);
    const filters = {};
    
    for (let [key, value] of formData.entries()) {
        if (value) {
            filters[key] = value;
        }
    }
    showNotification('Filters applied successfully', 'success');
}

// Initialize action buttons
function initializeActions() {
    // Only handle generic action buttons with explicit data-action
    const actionButtons = document.querySelectorAll('.action-btn[data-action]');
    
    actionButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            const action = this.textContent.trim();
            handleAction(action, this);
        });
    });
}

// Handle action button clicks
function handleAction(action, button) {
    console.log('Action clicked:', action);
    
    // Add loading state
    const originalText = button.innerHTML;
    button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Loading...';
    button.disabled = true;
    
    // Simulate action processing
    setTimeout(() => {
        // Reset button state
        button.innerHTML = originalText;
        button.disabled = false;
        
        // Show success message
        showNotification(`${action} completed successfully`, 'success');
    }, 2000);
}

// Initialize notifications
function initializeNotifications() {
    // Check for flash messages
    const flashMessages = document.querySelectorAll('.flash-message');
    
    flashMessages.forEach(message => {
        // Auto-hide flash messages after 5 seconds
        setTimeout(() => {
            message.style.opacity = '0';
            setTimeout(() => {
                message.remove();
            }, 300);
        }, 5000);
    });
}

// Show notification
function showNotification(message, type = 'info') {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `flash-message ${type}`;
    notification.textContent = message;
    
    // Add to page
    const container = document.querySelector('.flash-messages') || document.body;
    container.appendChild(notification);
    
    // Auto-hide after 5 seconds
    setTimeout(() => {
        notification.style.opacity = '0';
        setTimeout(() => {
            notification.remove();
        }, 300);
    }, 5000);
}

// Reload dashboard data (placeholder)
function reloadDashboardData(filters = {}) {
    // This function will be used to reload dashboard data via AJAX
    console.log('Reloading dashboard data with filters:', filters);
    
    // You can implement AJAX calls here to refresh dashboard content
    // fetch('/dashboard/api/stats', {
    //     method: 'POST',
    //     headers: {
    //         'Content-Type': 'application/json',
    //     },
    //     body: JSON.stringify(filters)
    // })
    // .then(response => response.json())
    // .then(data => {
    //     updateDashboard(data);
    // });
}

// Update dashboard with new data
function updateDashboard(data) {
    // Update stats cards
    if (data.stats) {
        updateStatsCards(data.stats);
    }
    
    // Update charts
    if (data.charts) {
        updateCharts(data.charts);
    }
    
    // Update recent activity
    if (data.activity) {
        updateRecentActivity(data.activity);
    }
}

// Update stats cards
function updateStatsCards(stats) {
    // Update each stat card with new data
    Object.keys(stats).forEach(key => {
        const card = document.querySelector(`[data-stat="${key}"]`);
        if (card) {
            const numberElement = card.querySelector('.stat-number');
            if (numberElement) {
                numberElement.textContent = stats[key];
            }
        }
    });
}

// Update charts (placeholder)
function updateCharts(chartData) {
    console.log('Updating charts with:', chartData);
    // Implement chart updates here
}

// Update recent activity
function updateRecentActivity(activity) {
    const activityContainer = document.querySelector('.recent-activity');
    if (!activityContainer) return;
    
    // Clear existing activity
    activityContainer.innerHTML = '';
    
    // Add new activity items
    activity.forEach(item => {
        const activityItem = createActivityItem(item);
        activityContainer.appendChild(activityItem);
    });
}

// Create activity item element
function createActivityItem(item) {
    const div = document.createElement('div');
    div.className = 'activity-item';
    div.innerHTML = `
        <div class="activity-icon">
            <i class="fas fa-${item.type === 'message' ? 'envelope' : 'user'}"></i>
        </div>
        <div class="activity-content">
            <div class="activity-title">${item.content}</div>
            <div class="activity-meta">${item.sender} • ${formatTimestamp(item.timestamp)}</div>
        </div>
    `;
    return div;
}

// Format timestamp
function formatTimestamp(timestamp) {
    const date = new Date(timestamp);
    const now = new Date();
    const diff = now - date;
    
    if (diff < 60000) { // Less than 1 minute
        return 'Just now';
    } else if (diff < 3600000) { // Less than 1 hour
        const minutes = Math.floor(diff / 60000);
        return `${minutes} minute${minutes > 1 ? 's' : ''} ago`;
    } else if (diff < 86400000) { // Less than 1 day
        const hours = Math.floor(diff / 3600000);
        return `${hours} hour${hours > 1 ? 's' : ''} ago`;
    } else {
        return date.toLocaleDateString();
    }
}

// Export functions for global use
window.Dashboard = {
    showNotification,
    reloadDashboardData,
    updateDashboard
};
