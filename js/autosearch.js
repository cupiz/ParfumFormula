/**
 * ParfumVault Auto-Search Module
 * 
 * Handles automatic online ingredient search when local results are empty.
 * Integrates with Python automation API via PHP bridge.
 */
console.log("🚀 Auto-Search Module Loaded v2.0");

var AutoSearch = (function() {
    // Configuration
    apiEndpoint: '/api.php?request=ingredient_autosearch',
    searchTimeout: 60000, // 60 seconds for scraping

    /**
     * Initialize auto-search functionality
     * Call this after DataTables is initialized
     */
    init: function (dataTable) {
        this.dataTable = dataTable;
        this.bindEvents();
    },

    /**
     * Bind event handlers
     */
    bindEvents: function () {
        // Listen for "Search Online" button click
        $(document).on('click', '#pv-autosearch-btn', (e) => {
            e.preventDefault();
            const searchTerm = $('#ing_search').val().trim();
            if (searchTerm) {
                this.searchOnline(searchTerm);
            }
        });

        // Listen for "Add to Library" button in modal
        $(document).on('click', '#pv-autosearch-add-btn', (e) => {
            e.preventDefault();
            this.addToLibrary();
        });
    },

    /**
     * Search for ingredient online
     */
    searchOnline: function (name) {
        const self = this;

        // Show loading state
        this.showLoading(`Searching PubChem & TGSC for "${name}"...`);

        $.ajax({
            url: this.apiEndpoint + '&action=search&name=' + encodeURIComponent(name),
            method: 'GET',
            timeout: this.searchTimeout,
            dataType: 'json',
            success: function (response) {
                if (response.success && response.ingredient) {
                    self.showPreview(response.ingredient, response.sources);
                } else {
                    self.showError(response.error || 'No data found online for this ingredient.');
                }
            },
            error: function (xhr, status, error) {
                if (status === 'timeout') {
                    self.showError('Search timed out. The servers may be slow. Please try again.');
                } else {
                    self.showError('Failed to connect to automation service: ' + error);
                }
            }
        });
    },

    /**
     * Show loading spinner in modal
     */
    showLoading: function (message) {
        const modal = this.getOrCreateModal();
        modal.find('.modal-body').html(`
            <div class="text-center py-4">
                <div class="spinner-border text-primary mb-3" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
                <p class="text-muted">${message}</p>
                <small class="text-muted">This may take up to 30 seconds...</small>
            </div>
        `);
        modal.find('.modal-footer').hide();
        modal.modal('show');
    },

    /**
     * Show preview of found ingredient
     */
    showPreview: function (ingredient, sources) {
        const modal = this.getOrCreateModal();

        // Store ingredient data for adding
        this.pendingIngredient = ingredient;

        // Build preview HTML
        let sourceBadges = '';
        if (sources) {
            if (sources.tgsc) sourceBadges += '<span class="badge bg-success me-1">TGSC</span>';
            if (sources.pubchem) sourceBadges += '<span class="badge bg-primary me-1">PubChem</span>';
        }

        const html = `
            <div class="alert alert-success">
                <i class="fas fa-check-circle me-2"></i>
                <strong>Found!</strong> Data retrieved from: ${sourceBadges}
            </div>
            
            <table class="table table-sm table-bordered">
                <tbody>
                    <tr>
                        <th style="width: 140px;">Name</th>
                        <td><strong>${this.escapeHtml(ingredient.name)}</strong></td>
                    </tr>
                    <tr>
                        <th>CAS Number</th>
                        <td>${ingredient.cas || '<em class="text-muted">Not found</em>'}</td>
                    </tr>
                    <tr>
                        <th>Formula</th>
                        <td>${ingredient.formula || '<em class="text-muted">Not found</em>'}</td>
                    </tr>
                    <tr>
                        <th>Molecular Weight</th>
                        <td>${ingredient.molecular_weight || '<em class="text-muted">Not found</em>'}</td>
                    </tr>
                    <tr>
                        <th>IUPAC Name</th>
                        <td><small>${ingredient.iupac_name || '<em class="text-muted">Not found</em>'}</small></td>
                    </tr>
                    <tr>
                        <th>Odor Description</th>
                        <td>${ingredient.odor_description || '<em class="text-muted">Not found</em>'}</td>
                    </tr>
                    <tr>
                         <th>Tenacity</th>
                         <td>${ingredient.tenacity || '<em class="text-muted">Not found</em>'}</td>
                    </tr>
                    <tr>
                         <th>Flash Point</th>
                         <td>${ingredient.flash_point ? ingredient.flash_point + (ingredient.flash_point.includes('°') ? '' : ' °C') : '<em class="text-muted">Not found</em>'}</td>
                    </tr>
                     <tr>
                         <th>LogP</th>
                         <td>${ingredient.logp || '<em class="text-muted">Not found</em>'}</td>
                    </tr>
                    <tr>
                         <th>Solubility</th>
                         <td>${ingredient.solubility || '<em class="text-muted">Not found</em>'}</td>
                    </tr>
                    ${ingredient.fema ? `<tr><th>FEMA</th><td>${ingredient.fema}</td></tr>` : ''}
                    ${ingredient.einecs ? `<tr><th>EINECS</th><td>${ingredient.einecs}</td></tr>` : ''}
                    ${ingredient.reach ? `<tr><th>REACH</th><td>${ingredient.reach}</td></tr>` : ''}
                    ${ingredient.shelf_life ? `<tr><th>Shelf Life</th><td>${ingredient.shelf_life} month(s)</td></tr>` : ''}
                </tbody>
            </table>
        `;

        modal.find('.modal-body').html(html);
        modal.find('.modal-footer').show();
        modal.find('#pv-autosearch-add-btn').show();
    },

    /**
     * Show error message
     */
    showError: function (message) {
        const modal = this.getOrCreateModal();
        modal.find('.modal-body').html(`
            <div class="alert alert-warning mb-0">
                <i class="fas fa-exclamation-triangle me-2"></i>
                ${this.escapeHtml(message)}
            </div>
        `);
        modal.find('.modal-footer').show();
        modal.find('#pv-autosearch-add-btn').hide();
    },

    /**
     * Add pending ingredient to library
     */
    addToLibrary: function () {
        const self = this;

        if (!this.pendingIngredient) {
            this.showError('No ingredient data to add.');
            return;
        }

        const addBtn = $('#pv-autosearch-add-btn');
        addBtn.prop('disabled', true).html('<span class="spinner-border spinner-border-sm me-2"></span>Adding...');

        $.ajax({
            url: this.apiEndpoint + '&action=add',
            method: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({ ingredient: this.pendingIngredient }),
            dataType: 'json',
            success: function (response) {
                if (response.success) {
                    // Show success toast
                    $('#toast-title').html('<i class="fa-solid fa-circle-check me-2"></i>' + response.message);
                    $('.toast-header').removeClass().addClass('toast-header alert-success');
                    $('.toast').toast('show');

                    // Close modal and refresh table
                    self.getOrCreateModal().modal('hide');
                    self.dataTable.ajax.reload(null, false);

                    // Clear search
                    $('#ing_search').val('');
                    self.pendingIngredient = null;
                } else {
                    self.showError(response.error || 'Failed to add ingredient.');
                    addBtn.prop('disabled', false).html('<i class="fas fa-plus me-2"></i>Add to My Library');
                }
            },
            error: function (xhr, status, error) {
                self.showError('Failed to add ingredient: ' + error);
                addBtn.prop('disabled', false).html('<i class="fas fa-plus me-2"></i>Add to My Library');
            }
        });
    },

    /**
     * Get or create the auto-search modal
     */
    getOrCreateModal: function () {
        let modal = $('#pv-autosearch-modal');

        if (modal.length === 0) {
            $('body').append(`
                <div class="modal fade" id="pv-autosearch-modal" tabindex="-1" aria-hidden="true">
                    <div class="modal-dialog modal-lg">
                        <div class="modal-content">
                            <div class="modal-header">
                                <h5 class="modal-title">
                                    <i class="fas fa-globe me-2"></i>Online Ingredient Search
                                </h5>
                                <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                            </div>
                            <div class="modal-body">
                                <!-- Dynamic content -->
                            </div>
                            <div class="modal-footer">
                                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                                <button type="button" class="btn btn-primary" id="pv-autosearch-add-btn">
                                    <i class="fas fa-plus me-2"></i>Add to My Library
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            `);
            modal = $('#pv-autosearch-modal');
        }

        return modal;
    },

    /**
     * Escape HTML to prevent XSS
     */
    escapeHtml: function (text) {
        if (!text) return '';
        return String(text)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    },

    /**
     * Generate "Search Online" button HTML for zeroRecords
     */
    getZeroRecordsHtml: function () {
        return `
            <div class="alert alert-warning mt-2">
                <i class="fa-solid fa-triangle-exclamation mx-2"></i>
                <strong>Nothing found in your library.</strong>
            </div>
            <div class="text-center my-3">
                <button type="button" class="btn btn-outline-primary" id="pv-autosearch-btn">
                    <i class="fas fa-globe me-2"></i>Search Online (PubChem & TGSC)
                </button>
            </div>
            <p class="text-muted text-center small">
                Can't find what you're looking for? Search our online database of 100M+ chemical compounds.
            </p>
        `;
    }
};
