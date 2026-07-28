// Modern WhatsApp Groups List JavaScript
let assemblies = [];
let currentGroups = [];
let filteredGroups = [];
let currentPage = 1;
let itemsPerPage = 10;
let sortBy = 'phone_count';
let sortOrder = 'desc';

// Initialize when page loads
document.addEventListener('DOMContentLoaded', function() {
    console.log('Modern WhatsApp Groups List page loaded');
    
    // Load assemblies
    loadAssemblies();
    
    // Initialize event listeners
    initializeEventListeners();
});

// Initialize event listeners
function initializeEventListeners() {
    // Search functionality
    const searchInput = document.getElementById('groupSearch');
    if (searchInput) {
        searchInput.addEventListener('input', debounce(filterGroups, 300));
    }
}

// Debounce function for search
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Load assemblies from API
async function loadAssemblies() {
    try {
        showLoadingState();
        
        const response = await fetch('/api/assemblies');
        const data = await response.json();
        
        if (data.success) {
            assemblies = data.assemblies;
            populateAssemblySelect();
        } else {
            console.error('Failed to load assemblies:', data.message);
            showError('Failed to load assemblies: ' + data.message);
        }
    } catch (error) {
        console.error('Error loading assemblies:', error);
        showError('Error loading assemblies: ' + error.message);
    } finally {
        hideLoadingState();
    }
}



// Populate assembly select dropdown
function populateAssemblySelect() {
    try {
        const assemblySelect = document.getElementById('assemblySelect');
        if (!assemblySelect) return;
        
        // Clear existing options except the first one
        assemblySelect.innerHTML = '<option value="">Choose an Assembly</option>';
        
        // Add assembly options
        assemblies.forEach(assembly => {
            const option = document.createElement('option');
            option.value = assembly.name;
            option.textContent = assembly.name;
            assemblySelect.appendChild(option);
        });
        
        console.log('Assembly select populated with', assemblies.length, 'assemblies');
        
    } catch (error) {
        console.error('Error populating assembly select:', error);
    }
}

// Load groups for selected assembly
async function loadGroupsForAssembly() {
    try {
        const assemblySelect = document.getElementById('assemblySelect');
        const selectedAssembly = assemblySelect.value;
        
        if (!selectedAssembly) {
            hideAllSections();
            return;
        }
        
        console.log('Loading groups for assembly:', selectedAssembly);
        
        // Show loading state
        showLoadingState();
        
        // Prepare request data
        const requestData = {
            assembly_name: selectedAssembly
        };
        
        console.log('Sending request to /api/assembly-groups with data:', requestData);
        
        // Make API call to get groups for the assembly
        const response = await fetch('/api/assembly-groups', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(requestData)
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        
        if (data.success) {
            console.log('Assembly groups loaded:', data.groups);
            currentGroups = data.groups;
            filteredGroups = [...currentGroups];
            currentPage = 1;
            displayGroupsData(data.groups, data.summary);
        } else {
            throw new Error(data.message || 'Failed to load assembly groups');
        }
        
    } catch (error) {
        hideLoadingState();
        console.error('Error loading assembly groups:', error);
        showError('Error loading assembly groups: ' + error.message);
    }
}

// Display groups data
function displayGroupsData(groups, summary) {
    try {
        // Hide loading state
        hideLoadingState();
        
        if (!groups || groups.length === 0) {
            showNoDataState();
            return;
        }
        
        // Update summary cards
        updateSummaryCards(summary);
        
        // Display groups table (sorted by phone count by default)
        displayGroupsTable();
        
        // Show groups sections
        showGroupsSections();
        
        console.log('Groups data displayed successfully');
        
    } catch (error) {
        console.error('Error displaying groups data:', error);
        showError('Error displaying groups data: ' + error.message);
    }
}

// Update summary cards
function updateSummaryCards(summary) {
    try {
        const totalGroupsElement = document.getElementById('totalGroupsCount');
        const totalMembersElement = document.getElementById('totalMembersCount');
        const totalPhonesElement = document.getElementById('totalPhonesCount');
        
        if (totalGroupsElement) {
            totalGroupsElement.textContent = (summary.total_groups || 0).toLocaleString();
        }
        
        if (totalMembersElement) {
            totalMembersElement.textContent = (summary.total_members || 0).toLocaleString();
        }
        
        if (totalPhonesElement) {
            totalPhonesElement.textContent = (summary.total_phones || 0).toLocaleString();
        }
        
        console.log('Summary cards updated:', summary);
        
    } catch (error) {
        console.error('Error updating summary cards:', error);
    }
}



// Filter groups based on search
function filterGroups() {
    try {
        const searchInput = document.getElementById('groupSearch');
        const searchTerm = searchInput ? searchInput.value.toLowerCase().trim() : '';
        
        if (!searchTerm) {
            filteredGroups = [...currentGroups];
        } else {
            filteredGroups = currentGroups.filter(group => {
                const groupName = (group.group_name || '').toLowerCase();
                return groupName.includes(searchTerm);
            });
        }
        
        // Sort by phone count (highest to lowest) and reset to first page
        filteredGroups.sort((a, b) => (b.phone_count || 0) - (a.phone_count || 0));
        currentPage = 1;
        
        // Display filtered groups
        displayGroupsTable();
        
        console.log('Groups filtered. Search term:', searchTerm, 'Results:', filteredGroups.length);
        
    } catch (error) {
        console.error('Error filtering groups:', error);
    }
}

// Display groups table with pagination
function displayGroupsTable() {
    try {
        const tableBody = document.getElementById('groupsTableBody');
        if (!tableBody) {
            console.error('Groups table body not found');
            return;
        }
        
        if (!filteredGroups || filteredGroups.length === 0) {
            tableBody.innerHTML = '<tr><td colspan="7" class="text-center">No groups found</td></tr>';
            updateTableInfo();
            updatePagination();
            return;
        }
        
        // Calculate pagination
        const totalPages = Math.ceil(filteredGroups.length / itemsPerPage);
        const startIndex = (currentPage - 1) * itemsPerPage;
        const endIndex = Math.min(startIndex + itemsPerPage, filteredGroups.length);
        const pageGroups = filteredGroups.slice(startIndex, endIndex);
        
        let html = '';
        
        pageGroups.forEach((group, index) => {
            const rank = startIndex + index + 1;
            const groupName = group.group_name || 'Unknown Group';
            const phoneCount = group.phone_count || 0;
            const memberCount = group.member_count || 0;
            const fileSize = formatFileSize(group.file_size || 0);
            const lastUpdated = formatTimestamp(group.last_updated || group.timestamp);
            
            html += `
                <tr>
                    <td class="rank">#${rank}</td>
                    <td class="group-name">
                        <div class="group-name-text" title="${groupName}">${groupName}</div>
                    </td>
                    <td class="phone-count">${phoneCount.toLocaleString()}</td>
                    <td class="member-count">${memberCount.toLocaleString()}</td>
                    <td class="file-size">${fileSize}</td>
                    <td class="last-updated">${lastUpdated}</td>
                    <td class="actions">
                        <button class="btn btn-success btn-sm" onclick="downloadGroupExcel('${groupName}', '${group.assembly || ''}', '${group.filename || ''}')" title="Download Excel with Phone Numbers">
                            <i class="fas fa-download"></i> Download
                        </button>
                    </td>
                </tr>
            `;
        });
        
        tableBody.innerHTML = html;
        
        // Update table info and pagination
        updateTableInfo();
        updatePagination();
        
        console.log('Groups table populated with', pageGroups.length, 'groups (page', currentPage, 'of', totalPages, ')');
        
    } catch (error) {
        console.error('Error displaying groups table:', error);
        showError('Error displaying groups table: ' + error.message);
    }
}

// Update table info
function updateTableInfo() {
    try {
        const tableInfo = document.getElementById('tableInfo');
        if (!tableInfo) return;
        
        const total = filteredGroups ? filteredGroups.length : 0;
        const startIndex = (currentPage - 1) * itemsPerPage + 1;
        const endIndex = Math.min(currentPage * itemsPerPage, total);
        
        if (total === 0) {
            tableInfo.textContent = 'No groups found';
        } else {
            tableInfo.textContent = `Showing ${startIndex}-${endIndex} of ${total.toLocaleString()} groups`;
        }
        
    } catch (error) {
        console.error('Error updating table info:', error);
    }
}

// Update pagination
function updatePagination() {
    try {
        const totalPages = Math.ceil((filteredGroups ? filteredGroups.length : 0) / itemsPerPage);
        const pageInfo = document.getElementById('pageInfo');
        const prevBtn = document.getElementById('prevBtn');
        const nextBtn = document.getElementById('nextBtn');
        
        if (pageInfo) {
            pageInfo.textContent = `Page ${currentPage} of ${totalPages}`;
        }
        
        if (prevBtn) {
            prevBtn.disabled = currentPage <= 1;
        }
        
        if (nextBtn) {
            nextBtn.disabled = currentPage >= totalPages;
        }
        
    } catch (error) {
        console.error('Error updating pagination:', error);
    }
}

// Previous page
function previousPage() {
    if (currentPage > 1) {
        currentPage--;
        displayGroupsTable();
    }
}

// Next page
function nextPage() {
    const totalPages = Math.ceil((filteredGroups ? filteredGroups.length : 0) / itemsPerPage);
    if (currentPage < totalPages) {
        currentPage++;
        displayGroupsTable();
    }
}

// Format file size
function formatFileSize(bytes) {
    try {
        if (bytes === 0) return '0 B';
        
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        
        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
        
    } catch (error) {
        console.error('Error formatting file size:', error);
        return 'Unknown';
    }
}

// Format timestamp
function formatTimestamp(timestamp) {
    try {
        if (!timestamp) return 'Unknown';
        
        // Try to parse the timestamp
        const date = new Date(timestamp);
        if (isNaN(date.getTime())) {
            return timestamp; // Return as-is if can't parse
        }
        
        // Format as readable date and time
        return date.toLocaleString('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
        
    } catch (error) {
        console.error('Error formatting timestamp:', error);
        return timestamp || 'Unknown';
    }
}

// Show groups sections
function showGroupsSections() {
    try {
        const groupsSummary = document.getElementById('groupsSummary');
        const groupsListSection = document.getElementById('groupsListSection');
        
        if (groupsSummary) {
            groupsSummary.style.display = 'grid';
        }
        
        if (groupsListSection) {
            groupsListSection.style.display = 'block';
        }
        
        console.log('Groups sections displayed');
        
    } catch (error) {
        console.error('Error showing groups sections:', error);
    }
}

// Hide all sections
function hideAllSections() {
    try {
        const groupsSummary = document.getElementById('groupsSummary');
        const groupsListSection = document.getElementById('groupsListSection');
        const loadingState = document.getElementById('loadingState');
        const noDataState = document.getElementById('noDataState');
        
        if (groupsSummary) groupsSummary.style.display = 'none';
        if (groupsListSection) groupsListSection.style.display = 'none';
        if (loadingState) loadingState.style.display = 'none';
        if (noDataState) noDataState.style.display = 'none';
        
        console.log('All sections hidden');
        
    } catch (error) {
        console.error('Error hiding sections:', error);
    }
}

// Show loading state
function showLoadingState() {
    try {
        hideAllSections();
        
        const loadingState = document.getElementById('loadingState');
        if (loadingState) {
            loadingState.style.display = 'flex';
        }
        
        console.log('Loading state shown');
        
    } catch (error) {
        console.error('Error showing loading state:', error);
    }
}

// Hide loading state
function hideLoadingState() {
    try {
        const loadingState = document.getElementById('loadingState');
        if (loadingState) {
            loadingState.style.display = 'none';
        }
        
        console.log('Loading state hidden');
        
    } catch (error) {
        console.error('Error hiding loading state:', error);
    }
}

// Show no data state
function showNoDataState() {
    try {
        hideAllSections();
        
        const noDataState = document.getElementById('noDataState');
        if (noDataState) {
            noDataState.style.display = 'flex';
        }
        
        console.log('No data state shown');
        
    } catch (error) {
        console.error('Error showing no data state:', error);
    }
}

// Download group Excel file with phone numbers
function downloadGroupExcel(groupName, assembly, filename) {
    try {
        console.log('Downloading Excel for group:', { groupName, assembly, filename });
        
        if (!groupName || !assembly) {
            showError('Group name and assembly are required');
            return;
        }
        
        // Create download URL
        const downloadUrl = `/api/download-group-excel?group=${encodeURIComponent(groupName)}&assembly=${encodeURIComponent(assembly)}&filename=${encodeURIComponent(filename)}`;
        console.log('Download URL:', downloadUrl);
        
        // Create a temporary link and trigger download
        const link = document.createElement('a');
        link.href = downloadUrl;
        link.download = `${groupName}_phone_numbers.xlsx`;
        link.style.display = 'none';
        
        // Add to DOM, click, and remove
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        
        console.log('Download initiated for group:', groupName);
        showSuccess(`Download started for ${groupName} phone numbers!`);
        
    } catch (error) {
        console.error('Error downloading group Excel:', error);
        showError('Error downloading group Excel: ' + error.message);
    }
}

// Download all phone numbers from all groups
function downloadAllPhoneNumbers() {
    try {
        console.log('Starting download of all phone numbers...');
        
        const assemblySelect = document.getElementById('assemblySelect');
        const selectedAssembly = assemblySelect.value;
        
        if (!selectedAssembly) {
            showError('Please select an assembly first');
            return;
        }
        
        if (!currentGroups || currentGroups.length === 0) {
            showError('No groups data available for download');
            return;
        }
        
        // Get total phone count for better user feedback
        const totalPhones = document.getElementById('totalPhonesCount').textContent || '0';
        const phoneCount = totalPhones.replace(/,/g, '');
        
        // Show loading state for all download buttons
        const downloadBtns = document.querySelectorAll('[onclick="downloadAllPhoneNumbers()"]');
        const originalTexts = [];
        
        downloadBtns.forEach((btn, index) => {
            originalTexts[index] = btn.innerHTML;
            btn.disabled = true;
            btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processing...';
        });
        
        // Create download URL
        const downloadUrl = `/api/download-all-phone-numbers?assembly=${encodeURIComponent(selectedAssembly)}`;
        console.log('Download URL:', downloadUrl);
        
        // Create a temporary link and trigger download
        const link = document.createElement('a');
        link.href = downloadUrl;
        link.download = `${selectedAssembly}_all_phone_numbers.xlsx`;
        link.style.display = 'none';
        
        // Add to DOM, click, and remove
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        
        console.log('Download initiated for all phone numbers');
        showSuccess(`📱 Download started! Processing ${phoneCount} phone numbers from ${selectedAssembly}...`);
        
        // Restore button states
        setTimeout(() => {
            downloadBtns.forEach((btn, index) => {
                btn.disabled = false;
                btn.innerHTML = originalTexts[index];
            });
        }, 3000);
        
    } catch (error) {
        console.error('Error downloading all phone numbers:', error);
        showError('Error downloading all phone numbers: ' + error.message);
        
        // Restore button states
        const downloadBtns = document.querySelectorAll('[onclick="downloadAllPhoneNumbers()"]');
        downloadBtns.forEach(btn => {
            btn.disabled = false;
            btn.innerHTML = '<i class="fas fa-download"></i> Download All Phone Numbers';
        });
    }
}

// Download groups list
function downloadGroupsList() {
    try {
        console.log('Starting download of groups list...');
        
        if (!currentGroups || currentGroups.length === 0) {
            showError('No groups data available for download');
            return;
        }
        
        // Prepare CSV data
        const csvData = [];
        
        // Add header row
        csvData.push([
            'Rank',
            'Group Name',
            'Phone Numbers',
            'Members',
            'File Size',
            'Last Updated',
            'Assembly'
        ]);
        
        // Add data rows (sorted by phone count)
        const sortedGroups = [...currentGroups].sort((a, b) => (b.phone_count || 0) - (a.phone_count || 0));
        
        sortedGroups.forEach((group, index) => {
            const rank = index + 1;
            const groupName = group.group_name || 'Unknown Group';
            const phoneCount = group.phone_count || 0;
            const memberCount = group.member_count || 0;
            const fileSize = formatFileSize(group.file_size || 0);
            const lastUpdated = formatTimestamp(group.last_updated || group.timestamp);
            const assembly = group.assembly || 'Unknown';
            
            csvData.push([
                rank,
                groupName,
                phoneCount,
                memberCount,
                fileSize,
                lastUpdated,
                assembly
            ]);
        });
        
        // Convert to CSV format
        const csvContent = csvData.map(row => 
            row.map(cell => `"${cell.toString().replace(/"/g, '""')}"`).join(',')
        ).join('\n');
        
        // Create and download file
        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
        const link = document.createElement('a');
        const url = URL.createObjectURL(blob);
        
        // Generate filename with current date and assembly info
        const currentDate = new Date().toISOString().split('T')[0];
        const selectedAssembly = document.getElementById('assemblySelect').value || 'all';
        const filename = `groups_list_${selectedAssembly}_${currentDate}.csv`;
        
        link.setAttribute('href', url);
        link.setAttribute('download', filename);
        link.style.visibility = 'hidden';
        
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        
        // Clean up
        URL.revokeObjectURL(url);
        
        console.log('Groups list downloaded successfully as:', filename);
        showSuccess(`✅ Groups list downloaded successfully! File: ${filename}`);
        
    } catch (error) {
        console.error('Error downloading groups list:', error);
        showError('Error downloading groups list: ' + error.message);
    }
}

// Go back to main analysis page
function goBack() {
    window.location.href = '/user/whatsapp-analysis';
}

// Show success message
function showSuccess(message) {
    try {
        const modal = document.getElementById('successModal');
        const messageElement = document.getElementById('successMessage');
        
        if (modal && messageElement) {
            messageElement.textContent = message;
            modal.style.display = 'flex';
        } else {
            console.warn('Success modal not found, falling back to alert');
            alert('Success: ' + message);
        }
        
    } catch (error) {
        console.error('Error showing success message:', error);
        alert('Success: ' + message);
    }
}

// Show error message
function showError(message) {
    try {
        const modal = document.getElementById('errorModal');
        const messageElement = document.getElementById('errorMessage');
        
        if (modal && messageElement) {
            messageElement.textContent = message;
            modal.style.display = 'flex';
        } else {
            console.warn('Error modal not found, falling back to alert');
            alert('Error: ' + message);
        }
        
    } catch (error) {
        console.error('Error showing error message:', error);
        alert('Error: ' + message);
    }
}

// Close modal
function closeModal(modalId) {
    try {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.style.display = 'none';
        }
    } catch (error) {
        console.error('Error closing modal:', error);
    }
}

// Close modal when clicking outside
document.addEventListener('click', function(event) {
    if (event.target.classList.contains('modal')) {
        event.target.style.display = 'none';
    }
});

// Close modal with Escape key
document.addEventListener('keydown', function(event) {
    if (event.key === 'Escape') {
        const modals = document.querySelectorAll('.modal');
        modals.forEach(modal => {
            if (modal.style.display === 'flex') {
                modal.style.display = 'none';
            }
        });
    }
});

// Global functions for testing
window.testGroupsList = function() {
    console.log('Current state:', {
        assemblies: assemblies.length,
        currentGroups: currentGroups.length,
        filteredGroups: filteredGroups.length,
        currentPage
    });
};

window.testSearch = function(term) {
    const searchInput = document.getElementById('groupSearch');
    if (searchInput) {
        searchInput.value = term;
        filterGroups();
    }
};