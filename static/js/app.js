// MasterSales - HTMX + Alpine.js Configuration

// HTMX configuration
document.addEventListener('htmx:configRequest', function(event) {
    // Add CSRF token if needed in future
});

// HTMX error handling
document.addEventListener('htmx:responseError', function(event) {
    console.error('HTMX request failed:', event.detail);
});

// SortableJS integration for Kanban board
function initKanban() {
    document.querySelectorAll('.kanban-column').forEach(column => {
        if (typeof Sortable !== 'undefined') {
            new Sortable(column.querySelector('.kanban-cards'), {
                group: 'pipeline',
                animation: 150,
                ghostClass: 'dragging',
                dragClass: 'kanban-card',
                onEnd: function(evt) {
                    const contactId = evt.item.dataset.contactId;
                    const newStatus = evt.to.closest('.kanban-column').dataset.status;
                    // Send HTMX request to update status
                    htmx.ajax('POST', '/pipeline/move', {
                        values: {
                            contact_id: contactId,
                            new_status: newStatus,
                        },
                        target: '#pipeline-stats',
                        swap: 'innerHTML',
                    });
                },
            });
        }
    });
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    // Init Kanban if on pipeline page
    if (document.querySelector('.kanban-column')) {
        initKanban();
    }
});

// Alpine.js data stores
document.addEventListener('alpine:init', () => {
    Alpine.store('notifications', {
        items: [],
        add(message, type = 'info') {
            const id = Date.now();
            this.items.push({ id, message, type });
            setTimeout(() => this.remove(id), 5000);
        },
        remove(id) {
            this.items = this.items.filter(item => item.id !== id);
        },
    });
});
