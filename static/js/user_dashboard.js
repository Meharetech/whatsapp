// Modern User Dashboard JavaScript
let dashboardStats = null;
const DASHBOARD_CACHE_KEY = 'dashboardStatsCache';
const DASHBOARD_CACHE_TIME = 5 * 60 * 1000; // 5 minutes in ms

// Initialize when page loads
document.addEventListener('DOMContentLoaded', function() {
    // Add refresh button handler if present
    const refreshBtn = document.querySelector('.refresh-btn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', function() {
            clearDashboardCache();
            loadDashboardStats(true);
        });
    }
    
    // Add export button handler
    const exportBtn = document.querySelector('.export-btn');
    if (exportBtn) {
        exportBtn.addEventListener('click', function() {
            exportDashboardData();
        });
    }
    
    loadDashboardStats();
});

// Load dashboard statistics
async function loadDashboardStats(forceRefresh = false) {
    try {
        // Try to use cache unless forceRefresh is true
        if (!forceRefresh) {
            const cached = sessionStorage.getItem(DASHBOARD_CACHE_KEY);
            if (cached) {
                const { stats, timestamp } = JSON.parse(cached);
                if (Date.now() - timestamp < DASHBOARD_CACHE_TIME) {
                    dashboardStats = stats;
                    displayDashboardStats(stats);
                    return;
                }
            }
        }
        // Show loading state
        showLoading();
        const response = await fetch('/api/accurate-dashboard-stats');
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        const data = await response.json();
        if (data.success) {
            dashboardStats = data.stats;
            // Cache the result
            sessionStorage.setItem(DASHBOARD_CACHE_KEY, JSON.stringify({ stats: data.stats, timestamp: Date.now() }));
            displayDashboardStats(data.stats);
        } else {
            showError('Failed to load dashboard stats: ' + (data.message || 'Unknown error'));
        }
    } catch (error) {
        console.error('Dashboard stats error:', error);
        showError('Error loading dashboard stats: ' + error.message);
    }
}

function clearDashboardCache() {
    sessionStorage.removeItem(DASHBOARD_CACHE_KEY);
}

// Display dashboard statistics
function displayDashboardStats(stats) {
    // Update main stats cards
    document.getElementById('totalAssemblies').textContent = stats.total_assemblies;
    document.getElementById('totalGroups').textContent = stats.total_groups;
    document.getElementById('totalPhones').textContent = stats.total_phones;
    
    // Update quick stats in header
    document.getElementById('quickTotalAssemblies').textContent = stats.total_assemblies;
    document.getElementById('quickTotalGroups').textContent = stats.total_groups;
    document.getElementById('quickTotalPhones').textContent = stats.total_phones;
    
    // Update total messages if available
    const totalMessages = document.getElementById('totalMessages');
    if (totalMessages) {
        totalMessages.textContent = stats.total_messages || '0';
    }
    
    // Display assembly breakdown
    displayAssemblyBreakdown(stats.assemblies);
}

// Display assembly breakdown
function displayAssemblyBreakdown(assemblies) {
    const container = document.getElementById('assemblyBreakdown');
    
    if (assemblies.length === 0) {
        container.innerHTML = '<p class="no-data">No assemblies found.</p>';
        return;
    }
    
    let html = '<div class="assembly-grid">';
    
    assemblies.forEach((assembly, index) => {
        html += `
            <div class="assembly-card" data-assembly-id="${index}">
                <div class="assembly-header clickable" onclick="toggleAssemblyDetails(${index})">
                    <div class="header-left">
                        <h4><i class="fas fa-building"></i> ${assembly.name}</h4>
                        <i class="fas fa-chevron-down toggle-icon" id="toggle-icon-${index}"></i>
                    </div>
                    <div class="assembly-stats">
                        <span class="stat-badge groups">
                            <i class="fas fa-users"></i> ${assembly.groups_count} Groups
                        </span>
                        <span class="stat-badge phones">
                            <i class="fas fa-phone"></i> ${assembly.phones_count} Phones
                        </span>
                    </div>
                </div>
                <div class="assembly-breakdown" id="breakdown-${index}" style="display: none;">
                    <div class="breakdown-content">
                       
                        <div class="groups-list">
                            <h5>All Groups in ${assembly.name}:</h5>
        `;
        
        if (assembly.groups.length > 0) {
            // Show all groups in the breakdown
            assembly.groups.forEach(group => {
                const cleanName = cleanGroupName(group.name);
                html += `
                    <div class="group-item">
                        <span class="group-name">${cleanName}</span>
                        <span class="group-phones">${group.phones_count} phones</span>
                    </div>
                `;
            });
        } else {
            html += '<p class="no-groups">No groups found</p>';
        }
        
        html += `
                        </div>
                    </div>
                </div>
            </div>
        `;
    });
    
    html += '</div>';
    container.innerHTML = html;
}

// Real-time assembly & group filtering
function filterAssemblies(query) {
    const search = query.trim().toLowerCase();
    const cards = document.querySelectorAll('.assembly-card');
    
    cards.forEach(card => {
        const text = card.textContent.toLowerCase();
        if (text.includes(search)) {
            card.style.display = 'block';
        } else {
            card.style.display = 'none';
        }
    });
}

// Toggle assembly details
function toggleAssemblyDetails(assemblyId) {
    const breakdown = document.getElementById(`breakdown-${assemblyId}`);
    const toggleIcon = document.getElementById(`toggle-icon-${assemblyId}`);
    
    if (!breakdown) return;
    
    if (breakdown.style.display === 'none' || !breakdown.style.display) {
        // Show breakdown
        breakdown.style.display = 'block';
        if (toggleIcon) {
            toggleIcon.classList.remove('fa-chevron-down');
            toggleIcon.classList.add('fa-chevron-up');
        }
    } else {
        // Hide breakdown
        breakdown.style.display = 'none';
        if (toggleIcon) {
            toggleIcon.classList.remove('fa-chevron-up');
            toggleIcon.classList.add('fa-chevron-down');
        }
    }
}

// Show loading state
function showLoading() {
    const container = document.getElementById('assemblyBreakdown');
    container.innerHTML = `
        <div class="loading-spinner">
            <i class="fas fa-spinner fa-spin"></i> 
            <div>Loading assembly data...</div>
            <div class="loading-subtitle">Scanning Excel files and counting phone numbers</div>
        </div>
    `;
}

// Show error message
function showError(message) {
    const container = document.getElementById('assemblyBreakdown');
    container.innerHTML = `
        <div class="error-message">
            <i class="fas fa-exclamation-triangle"></i>
            <p>${message}</p>
            <button onclick="loadDashboardStats()" class="btn btn-primary btn-sm">
                <i class="fas fa-redo"></i> Retry
            </button>
        </div>
    `;
}

// Show success message
function showSuccess(message) {
    // You can implement a toast notification here
    console.log('Success:', message);
}

// Clean group name - remove file extension and timestamp
function cleanGroupName(fileName) {
    // Remove file extension (.xlsx, .xls, .csv)
    let cleanName = fileName.replace(/\.(xlsx|xls|csv)$/i, '');
    
    // Remove timestamp pattern (numbers followed by underscore)
    cleanName = cleanName.replace(/_\d+$/, '');
    
    // Remove "all_" suffix if present
    cleanName = cleanName.replace(/_all$/, '');
    
    // Remove multiple underscores and replace with spaces
    cleanName = cleanName.replace(/_+/g, ' ');
    
    // Capitalize first letter of each word
    cleanName = cleanName.replace(/\b\w/g, l => l.toUpperCase());
    
    return cleanName;
}

// Refresh dashboard function
function refreshDashboard() {
    const refreshBtn = document.querySelector('.refresh-btn');
    if (refreshBtn) {
        const icon = refreshBtn.querySelector('i');
        const text = refreshBtn.querySelector('span');
        
        // Show loading state
        icon.classList.add('fa-spin');
        text.textContent = 'Refreshing...';
        refreshBtn.disabled = true;
        
        // Clear cache and reload
        clearDashboardCache();
        loadDashboardStats(true).finally(() => {
            // Reset button state
            icon.classList.remove('fa-spin');
            text.textContent = 'Refresh';
            refreshBtn.disabled = false;
        });
    }
}

// Export dashboard data function
function exportDashboardData() {
    if (!dashboardStats) {
        showNotification('No data available to export', 'error');
        return;
    }
    
    try {
        // Create CSV content
        let csvContent = 'Assembly,Groups,Phone Numbers\n';
        
        dashboardStats.assemblies.forEach(assembly => {
            csvContent += `"${assembly.name}",${assembly.groups_count},${assembly.phones_count}\n`;
        });
        
        // Add summary row
        csvContent += `\nTOTAL,${dashboardStats.total_groups},${dashboardStats.total_phones}`;
        
        // Create and download file
        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
        const link = document.createElement('a');
        const url = URL.createObjectURL(blob);
        link.setAttribute('href', url);
        link.setAttribute('download', `dashboard_export_${new Date().toISOString().split('T')[0]}.csv`);
        link.style.visibility = 'hidden';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        
        showNotification('Dashboard data exported successfully!', 'success');
    } catch (error) {
        console.error('Export error:', error);
        showNotification('Failed to export data', 'error');
    }
}

// Show notification function
function showNotification(message, type = 'info') {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.innerHTML = `
        <div class="notification-content">
            <i class="fas fa-${type === 'success' ? 'check-circle' : type === 'error' ? 'exclamation-circle' : 'info-circle'}"></i>
            <span>${message}</span>
        </div>
    `;
    
    // Add styles
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: ${type === 'success' ? '#10b981' : type === 'error' ? '#ef4444' : '#3b82f6'};
        color: white;
        padding: 15px 20px;
        border-radius: 10px;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2);
        z-index: 1000;
        animation: slideInRight 0.3s ease-out;
        max-width: 300px;
    `;
    
    // Add to page
    document.body.appendChild(notification);
    
    // Remove after 3 seconds
    setTimeout(() => {
        notification.style.animation = 'slideOutRight 0.3s ease-in';
        setTimeout(() => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        }, 300);
    }, 3000);
}

// Add CSS animations for notifications
const style = document.createElement('style');
style.textContent = `
    @keyframes slideInRight {
        from {
            transform: translateX(100%);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
    
    @keyframes slideOutRight {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(100%);
            opacity: 0;
        }
    }
    
    .notification-content {
        display: flex;
        align-items: center;
        gap: 10px;
        font-weight: 500;
    }
`;
document.head.appendChild(style);


