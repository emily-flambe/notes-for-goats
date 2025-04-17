/**
 * Table Sorter - A simple script to make HTML tables sortable
 * 
 * Usage:
 * 1. Add the 'sortable' class and 'data-column' attribute to table headers that should be sortable
 * 2. Add a <span class="sort-icon">↕</span> inside each sortable header for the visual indicator
 * 3. Add 'data-sort-value' attributes to cells that need custom sort values
 */

function initTableSorter() {
    // Find all tables that should be sortable
    document.querySelectorAll('table').forEach(table => {
        const sortableHeaders = table.querySelectorAll('th.sortable');
        if (sortableHeaders.length === 0) return;
        
        // Add click event listeners to sortable headers
        sortableHeaders.forEach(header => {
            header.addEventListener('click', function() {
                const column = this.getAttribute('data-column');
                const isAscending = !this.classList.contains('sorted-asc');
                
                // Remove sorting classes from all headers
                sortableHeaders.forEach(h => {
                    h.classList.remove('sorted-asc', 'sorted-desc');
                    const icon = h.querySelector('.sort-icon');
                    if (icon) icon.textContent = '↕';
                });
                
                // Add sorting class to clicked header
                this.classList.add(isAscending ? 'sorted-asc' : 'sorted-desc');
                
                // Update sort icon
                const sortIcon = this.querySelector('.sort-icon');
                if (sortIcon) sortIcon.textContent = isAscending ? '↑' : '↓';
                
                // Get all rows and convert to array for sorting
                const tbody = table.querySelector('tbody');
                const rows = Array.from(tbody.querySelectorAll('tr'));
                
                // Find the index of the clicked column
                const headerRow = table.querySelector('thead tr');
                if (!headerRow) return;
                
                const headers = Array.from(headerRow.querySelectorAll('th'));
                const columnIndex = headers.indexOf(this);
                
                if (columnIndex === -1) return;
                
                // Sort rows based on the content of cells in the clicked column
                rows.sort((a, b) => {
                    const aCell = a.cells[columnIndex];
                    const bCell = b.cells[columnIndex];
                    
                    if (!aCell || !bCell) return 0;
                    
                    // Use data-sort-value if available, otherwise use text content
                    const aValue = aCell.getAttribute('data-sort-value') || 
                                  aCell.textContent.trim().toLowerCase();
                    const bValue = bCell.getAttribute('data-sort-value') || 
                                  bCell.textContent.trim().toLowerCase();
                    
                    // Compare the values
                    if (aValue < bValue) return isAscending ? -1 : 1;
                    if (aValue > bValue) return isAscending ? 1 : -1;
                    return 0;
                });
                
                // Remove all existing rows
                while (tbody.firstChild) {
                    tbody.removeChild(tbody.firstChild);
                }
                
                // Add sorted rows
                rows.forEach(row => {
                    tbody.appendChild(row);
                });
            });
        });
    });
}

// Initialize when DOM is fully loaded
document.addEventListener('DOMContentLoaded', function() {
    initTableSorter();
});
