// ===== APPLICATION STATE =====
const App = {
    config: {
        refreshInterval: 60,
        language: 'no'
    },
    state: {
        devices: [],
        settings: null,
        selectedDevices: new Set(),
        scanning: false,
        scanningDevices: new Set(),  // Track which devices are currently being scanned
        autoRefreshTimer: null,
        chartSelections: {}  // Store per-disk chart selections
    },
    charts: {},
    availableLanguages: [],
    translations: {}
};

// ===== LANGUAGE SYSTEM =====
App.loadAvailableLanguages = async function() {
    try {
        const response = await fetch('/api/languages');
        const data = await response.json();
        this.availableLanguages = data.languages;
        console.log('Available languages:', this.availableLanguages);
    } catch (error) {
        console.error('Error loading language list:', error);
    }
};

App.loadLanguage = async function(langCode) {
    try {
        const response = await fetch(`/api/language/${langCode}`);
        const data = await response.json();
        
        if (data.translations) {
            this.translations[langCode] = data.translations;
            console.log(`Loaded language: ${data.language_name} (${langCode})`);
            return true;
        }
        return false;
    } catch (error) {
        console.error(`Error loading language ${langCode}:`, error);
        return false;
    }
};

App.t = function(key) {
    const lang = App.config.language;
    if (App.translations[lang] && App.translations[lang][key]) {
        return App.translations[lang][key];
    }
    // Fallback to English
    if (lang !== 'en' && App.translations['en'] && App.translations['en'][key]) {
        return App.translations['en'][key];
    }
    // Return key if no translation found
    return key;
};

App.updateLanguage = function() {
    // Update all elements with data-i18n attribute
    document.querySelectorAll('[data-i18n]').forEach(el => {
        const key = el.getAttribute('data-i18n');
        el.textContent = this.t(key);
    });
    
    // Update documentation link based on language
    const docLink = document.getElementById('doc-link');
    if (docLink) {
        const lang = this.config.language;
        // Use same logic as backend: special case for Norwegian, otherwise documentation-{lang}.md
        if (lang === 'no') {
            docLink.href = '/dokumentasjon-no.md';
        } else {
            // Try language-specific file, fallback handled by 404 → English in browser
            docLink.href = `/documentation-${lang}.md`;
        }
    }
    
    // Re-render devices to update dynamic content
    if (this.state.devices.length > 0) {
        this.renderDevices();
    }
};

App.changeLanguage = async function(langCode) {
    // Load language if not already loaded
    if (!this.translations[langCode]) {
        const loaded = await this.loadLanguage(langCode);
        if (!loaded) {
            console.error(`Failed to load language: ${langCode}`);
            return;
        }
    }
    
    this.config.language = langCode;
    this.updateLanguage();
    
    // Save to backend
    try {
        await fetch('/api/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ language: langCode })
        });
    } catch (error) {
        console.error('Error saving language preference:', error);
    }
};

// ===== INITIALIZATION =====
App.init = async function(config) {
    this.config = { ...this.config, ...config };
    console.log('MoSMART Monitor initialized with config:', this.config);
    
    // Load available languages first
    await this.loadAvailableLanguages();
    
    // Always load English first as fallback
    if (this.config.language !== 'en') {
        await this.loadLanguage('en');
        console.log('Loaded English as fallback language');
    }
    
    // Load current language
    await this.loadLanguage(this.config.language);
    
    // Load settings and devices
    this.loadSettings().then(() => {
        this.refreshData();
        this.startAutoRefresh();
    });
    
    // Set initial language
    this.updateLanguage();
};

// ===== UTILITY FUNCTIONS =====
App.escapeHtml = function(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
};

// ===== DATA LOADING =====
App.loadSettings = async function() {
    try {
        const response = await fetch('/api/settings');
        if (!response.ok) throw new Error('Failed to load settings');
        
        this.state.settings = await response.json();
        console.log('Settings loaded:', this.state.settings);
        
        // Update config from settings
        if (this.state.settings.general) {
            this.config.refreshInterval = this.state.settings.general.polling_interval || 60;
            this.config.language = this.state.settings.general.language || 'no';
        }
        
        // Update emergency status indicator
        this.updateEmergencyStatusIndicator();
        
        return this.state.settings;
    } catch (error) {
        console.error('Error loading settings:', error);
        return null;
    }
};

App.refreshData = async function() {
    try {
        const response = await fetch('/api/devices/progressive');
        if (!response.ok) throw new Error('Failed to load devices');
        
        const data = await response.json();
        const newDevices = data.devices || [];
        const wasScanning = this.state.scanning;
        this.state.scanning = data.scanning || false;

        // Handle system event banner if present
        if (data.system_event && data.system_event.type === 'uncontrolled_shutdown') {
            this.state.lastSystemEvent = data.system_event;
            this.renderSystemEventBanner();
        } else {
            // Hide banner if no event
            const banner = document.getElementById('system-event-banner');
            if (banner) banner.style.display = 'none';
        }
        
        // If scan just started, mark all devices as scanning
        if (this.state.scanning && !wasScanning) {
            this.state.scanningDevices.clear();
            newDevices.forEach(d => this.state.scanningDevices.add(d.name));
        }
        
        // Merge new data with existing data (preserving old data until new data arrives)
        if (this.state.devices.length > 0) {
            // Create a map of existing devices
            const existingDevices = new Map();
            this.state.devices.forEach(d => existingDevices.set(d.name, d));
            
            // Update with new data where available
            this.state.devices = newDevices.map(newDevice => {
                const existing = existingDevices.get(newDevice.name);
                
                // If device has ANY valid data (model, serial, etc), mark as no longer scanning
                const hasValidData = newDevice.model || newDevice.serial || 
                                   (newDevice.health_score !== null && newDevice.health_score !== undefined);
                
                if (hasValidData) {
                    this.state.scanningDevices.delete(newDevice.name);
                    // If we have new data, use it; otherwise preserve existing
                    return newDevice.health_score !== null ? newDevice : (existing || newDevice);
                }
                
                // If no valid data yet and we have existing data, preserve it and remove scanning overlay
                if (existing && (existing.model || existing.health_score !== null)) {
                    this.state.scanningDevices.delete(newDevice.name);
                    return existing;
                }
                
                // New device with no data yet - show it but mark as scanning
                return newDevice;
            });
        } else {
            // First load - accept all new devices
            this.state.devices = newDevices;
            // Clear scanning state for devices with data
            newDevices.forEach(d => {
                if (d.model || d.health_score !== null) {
                    this.state.scanningDevices.delete(d.name);
                }
            });
        }
        
        // If scan completed, clear scanning markers
        if (!this.state.scanning && wasScanning) {
            this.state.scanningDevices.clear();
        }
        
        console.log('Devices loaded:', this.state.devices.length);
        console.log('Scanning:', this.state.scanning, 'Devices being scanned:', Array.from(this.state.scanningDevices));
        
        // Initialize selectedDevices with all devices on first load
        if (this.state.selectedDevices.size === 0 && this.state.devices.length > 0) {
            this.state.devices.forEach(d => this.state.selectedDevices.add(d.name));
        }
        
        // If no devices and not scanning, trigger a scan
        if (this.state.devices.length === 0 && !this.state.scanning) {
            console.log('No devices found, starting initial scan...');
            await fetch('/api/scan/start', { method: 'POST' });
            // Wait a bit and try again
            setTimeout(() => this.refreshData(), 3000);
            return;
        }
        
        // Update UI
        this.renderDevices();
        this.updateFilters();
        this.updateLastUpdate();
        
    } catch (error) {
        console.error('Error refreshing data:', error);
    }
};

App.renderSystemEventBanner = function() {
    const evt = this.state.lastSystemEvent;
    const banner = document.getElementById('system-event-banner');
    if (!banner || !evt) return;
    banner.style.display = 'flex';
    const tsEl = document.getElementById('system-event-date');
    const affectedEl = document.getElementById('system-event-affected');
    try {
        const date = new Date(evt.timestamp);
        tsEl.textContent = `Dato: ${date.toLocaleString('nb-NO')}`;
    } catch (e) {
        tsEl.textContent = `Dato: ${evt.timestamp}`;
    }
    const count = evt.affected_count || 0;
    affectedEl.textContent = `Påvirket disker: ${count}`;
};

App.forceScan = async function() {
    if (this.state.scanning) {
        alert(this.t('scanning_in_progress') || 'Scanning already in progress...');
        return;
    }
    
    try {
        // Mark all devices as scanning
        this.state.scanning = true;
        this.state.scanningDevices.clear();
        this.state.devices.forEach(d => this.state.scanningDevices.add(d.name));
        
        // Re-render to show scanning state
        this.renderDevices();
        
        alert(this.t('force_scan_started') || 'Force scan started! GDC freeze active for 5 minutes.');
        
        const response = await fetch('/api/force-scan', { method: 'POST' });
        if (!response.ok) {
            this.state.scanning = false;
            this.state.scanningDevices.clear();
            this.renderDevices();
            throw new Error('Failed to force scan');
        }
        
        // Refresh after a delay
        setTimeout(() => this.refreshData(), 2000);
        
    } catch (error) {
        console.error('Error forcing scan:', error);
        alert('Failed to start force scan');
    }
};

// ===== RENDERING =====
App.renderDevices = function() {
    const container = document.getElementById('devices-container');
    
    if (!this.state.devices || this.state.devices.length === 0) {
        container.innerHTML = `
            <div class="loading-spinner">
                <div class="spinner"></div>
                <p>${this.t('loading_smart')}</p>
            </div>
        `;
        return;
    }
    
    // Filter devices based on selections
    let devicesToShow = this.state.devices.filter(d => this.state.selectedDevices.has(d.name));
    
    // If nothing selected, show message instead of all devices
    if (devicesToShow.length === 0) {
        container.innerHTML = `
            <div style="text-align: center; padding: 40px;">
                <p>Ingen disker valgt. Bruk filtrene ovenfor for å velge hvilke disker som skal vises.</p>
            </div>
        `;
        return;
    }
    
    container.innerHTML = `
        <div class="devices-grid">
            ${devicesToShow.map(device => this.renderDeviceCard(device)).join('')}
        </div>
    `;
    
    // Add event delegation for buttons
    container.querySelectorAll('.btn-toggle-monitoring').forEach(btn => {
        btn.addEventListener('click', () => {
            console.log('Toggle monitoring clicked for:', btn.dataset.device);
            this.toggleMonitoring(btn.dataset.device);
        });
    });
    
    container.querySelectorAll('.btn-view-history').forEach(btn => {
        btn.addEventListener('click', () => {
            console.log('View history clicked for:', btn.dataset.device);
            this.viewHistory(btn.dataset.device);
        });
    });
    
    container.querySelectorAll('.btn-view-log').forEach(btn => {
        btn.addEventListener('click', () => {
            console.log('View log clicked for:', btn.dataset.device);
            this.viewLog(btn.dataset.device);
        });
    });
    
    container.querySelectorAll('.btn-print-label').forEach(btn => {
        btn.addEventListener('click', () => {
            console.log('Print label clicked for:', btn.dataset.device);
            this.printDiskLabel(btn.dataset.device);
        });
    });
};

// ===== DEVICE RENDERING (Backend Authority Architecture) =====

App.renderDeviceCard = function(device) {
    if (!device) return '';
    
    const status = this.getDeviceStatus(device);
    const diskIcon = device.is_ssd 
        ? `<img src="/static/img_ssd.png" class="disk-icon" alt="SSD">`
        : `<img src="/static/img_hdd.png" class="disk-icon" alt="HDD">`;
    const usbBadge = device.is_usb ? '<span class="usb-badge" title="USB device - Limited SMART support expected">🔌 USB</span>' : '';
    
    // Check if this device is currently being scanned
    const isScanning = this.state.scanningDevices.has(device.name);
    const scanningOverlay = isScanning ? this.renderScanningOverlay() : '';
    
    return `
        <div class="device-card status-${status}" data-device="${device.name}">
            ${scanningOverlay}
            ${this.renderDeviceHeader(device, status, diskIcon, usbBadge)}
            ${this.renderPastFailures(device)}
            ${this.renderCriticalHealthWarning(device)}
            ${this.renderSlowSmartWarning(device)}
            ${this.renderHealthScore(device)}
            ${this.renderEscalatedAttributes(device)}
            ${this.renderGDCBanner(device)}
            ${this.renderTemperature(device)}
            ${this.renderUsageMetrics(device)}
            ${this.renderSecondaryAttributes(device)}
            ${this.renderDeviceActions(device)}
        </div>
    `;
};

// ===== SCANNING OVERLAY =====
App.renderScanningOverlay = function() {
    return `
        <div class="scanning-overlay">
            <div class="scanning-message">
                <span class="scanning-spinner">⏳</span>
                <span class="scanning-text">${this.t('scanning_disk')}</span>
            </div>
        </div>
    `;
};

// ===== HEADER SECTION =====
App.renderDeviceHeader = function(device, status, diskIcon, usbBadge) {
    const isGDC = device.gdc_state && device.gdc_state.state !== 'OK';
    const displayModel = device.display_status || device.model || 'Unknown Model';
    
    return `
        <div class="device-header">
            <div>
                <div class="device-name">${diskIcon} ${device.name} ${usbBadge}</div>
                <div class="device-model" title="${this.t('tooltip_model')}">${displayModel}</div>
                ${device.capacity ? `<div class="device-capacity" title="${this.t('tooltip_capacity')}">${device.capacity}</div>` : ''}
            </div>
            <div class="device-status">
                ${isGDC ? `<span class="gdc-icon">💀</span>` : ''}
                <span class="status-badge ${status}" title="${this.t('tooltip_status')}">${this.t(status)}</span>
                <button class="btn-small btn-toggle-monitoring" data-device="${device.name}" 
                        style="margin-left: 8px;" 
                        title="${device.is_monitored ? 'Stopp overvåking' : 'Start overvåking'}">
                    ${device.is_monitored ? '⏸️' : '▶️'}
                </button>
            </div>
        </div>
    `;
};

// ===== PAST FAILURES WARNING =====
App.renderPastFailures = function(device) {
    if (!device.past_failures || device.past_failures.length === 0) {
        return '';
    }
    
    const failureList = device.past_failures.map(attr => {
        // Translate display_name if it's a translation key
        const translatedName = this.t(attr.display_name) || attr.display_name || attr.name;
        // Translate when_failed if it's a translation key
        const translatedWhen = this.t(attr.when_failed) || attr.when_failed;
        
        return `
            <div class="failure-item">
                <span class="failure-name">${translatedName}</span>
                <span class="failure-when">${translatedWhen}</span>
            </div>
        `;
    }).join('');
    
    return `
        <div class="past-failures-section">
            <div class="past-failures-header">
                <span class="warning-icon">⚠️</span>
                <span class="past-failures-title">${this.t('past_failures_detected')}</span>
            </div>
            <div class="past-failures-list">
                ${failureList}
            </div>
        </div>
    `;
};

// ===== CRITICAL HEALTH WARNING =====
App.renderCriticalHealthWarning = function(device) {
    if (device.health_score === null || device.health_score === undefined || device.health_score > 59) {
        return '';
    }
    
    // Critical level: ≤39 (red, pulsing)
    if (device.health_score <= 39) {
        return `
            <div class="critical-health-warning critical-level">
                <div class="critical-health-header">
                    <span class="warning-icon">🚨</span>
                    <span class="critical-health-title">${this.t('backup_immediately')}</span>
                </div>
            </div>
        `;
    }
    
    // Warning level: 40-59 (orange, calm)
    return `
        <div class="critical-health-warning warning-level">
            <div class="critical-health-header">
                <span class="warning-icon">⚠️</span>
                <span class="critical-health-title">${this.t('health_declining_backup_recommended')}</span>
            </div>
        </div>
    `;
};

// ===== SLOW SMART RESPONSE WARNING =====
App.renderSlowSmartWarning = function(device) {
    if (!device.slow_smart_response || !device.slow_smart_response.detected) {
        return '';
    }
    
    const responseTime = device.slow_smart_response.response_time;
    const threshold = device.slow_smart_response.threshold;
    
    return `
        <div class="slow-smart-warning">
            <div class="slow-smart-header">
                <span class="warning-icon">🐌</span>
                <span class="slow-smart-title">Langsom SMART-respons</span>
            </div>
            <div class="slow-smart-details">
                <div class="slow-smart-time">Responstid: ${responseTime}s (friske disker: <5s)</div>
                <div class="slow-smart-message">En frisk disk svarer på SMART-forespørsler på 1-3 sekunder. 
                Langsom respons kan indikere mekaniske problemer, selv om SMART-data viser 0 feil.</div>
            </div>
        </div>
    `;
};

// ===== HEALTH SCORE SECTION (Priority 1) =====
App.renderHealthScore = function(device) {
    if (device.health_score === null || device.health_score === undefined) {
        return '';
    }
    
    const healthState = device.health_state || 'unknown';
    
    // Map health state to emoji
    const stateEmoji = {
        'excellent': '🔵',  // 95-100: Blue
        'good': '🟢',       // 80-94: Green
        'acceptable': '🟡', // 60-79: Yellow
        'warning': '🟠',    // 40-59: Orange
        'poor': '🔴',       // 20-39: Red
        'critical': '🔴',   // 0-19: Red
        'dead': '💀',       // <0: Dead/Zombie
        'unknown': '❓'     // Unknown
    };
    
    const emoji = stateEmoji[healthState] || '❓';
    
    return `
        <div class="health-score-section health-${healthState}">
            <div class="health-score-label" title="${this.t('tooltip_health_score')}">🦉 ${this.t('health_score')}</div>
            <div class="health-score-value">
                <span class="health-score-emoji">${emoji}</span>
                <span class="health-score-number">${device.health_score}</span>
                <span class="health-score-max">/100</span>
            </div>
        </div>
    `;
};

// ===== ESCALATED ATTRIBUTES SECTION (Priority 2) =====
App.renderEscalatedAttributes = function(device) {
    if (!device.escalated_attributes || device.escalated_attributes.length === 0) {
        return '';
    }
    
    const escalatedHTML = device.escalated_attributes.map(attr => {
        const errorReason = attr.error_reason || null;
        const displayName = this.getAttributeDisplayName(attr.name, errorReason);
        const icon = this.getAttributeIcon(attr.name);
        
        return `
                <div class="escalated-item severity-${attr.severity}">
                <span class="escalated-icon">${icon}</span>
                    <span class="escalated-name" title="${this.getAttributeTooltip(attr.name, errorReason)}">${displayName}</span>
                <span class="escalated-value">${attr.value.toLocaleString()}</span>
            </div>
        `;
    }).join('');
    
    // Determine header and section class based on actual severity
    const hasCritical = device.escalated_attributes.some(attr => attr.severity === 'critical');
    const headerText = hasCritical ? this.t('critical_warnings') : this.t('warning');
    const sectionClass = hasCritical ? 'escalated-section-critical' : 'escalated-section-warning';
    
    return `
        <div class="escalated-section ${sectionClass}">
            <div class="escalated-header">⚠️ ${headerText}</div>
            <div class="escalated-list">${escalatedHTML}</div>
        </div>
    `;
};

// ===== GDC BANNER SECTION (Priority 3) =====
App.renderGDCBanner = function(device) {
    const gdcState = device.gdc_state?.state;
    
    if (!gdcState || gdcState === 'OK') {
        return '';
    }
    
    const gdcMessage = device.display_status || 'Ghost Drive Condition';
    const gdcSeverity = gdcState.toLowerCase();
    
    return `
        <div class="gdc-banner gdc-${gdcSeverity}">
            <div class="gdc-icon">💀</div>
            <div class="gdc-message">
                <div class="gdc-title">${gdcMessage}</div>
                <div class="gdc-subtitle">${this.t('gdc_identity_preserved')}</div>
            </div>
        </div>
    `;
};

// ===== TEMPERATURE SECTION (Priority 4) =====
App.renderTemperature = function(device) {
    if (device.temperature === null || device.temperature === undefined) {
        return '';
    }
    
    const tempClass = this.getTemperatureClass(device.temperature, device.is_ssd);
    
    // SMART ID 194 max temp (if available)
    const smartMaxTemp = device.max_temperature !== null && device.max_temperature !== undefined 
        ? `<div class="temp-max" title="${this.t('tooltip_smart_max_temp')}">SMART ID 194 max: ${device.max_temperature}°C</div>` 
        : '';
    
    // mosmart194 - observed max temp (always show if available)
    const mosmart194 = device.mosmart194 !== null && device.mosmart194 !== undefined
        ? `<div class="temp-mosmart194" title="${this.t('tooltip_mosmart194')}">mosmart194, max: ${device.mosmart194}°C</div>`
        : '';
    
    return `
        <div class="temperature-section">
            <div class="temp-header">
                <div class="temp-label" title="${this.t('tooltip_temperature')}">🌡 ${this.t('temperature')}</div>
                <div class="temp-value ${tempClass}">
                    <span class="temp-current">${device.temperature}</span>
                    <span class="temp-unit">°C</span>
                </div>
            </div>
            <div class="temp-details">
                ${mosmart194}
                ${smartMaxTemp}
            </div>
        </div>
    `;
};

// ===== USAGE METRICS SECTION (Priority 5) =====
App.renderUsageMetrics = function(device) {
    const metrics = [];
    const lifetimeRemaining = device.lifetime_remaining;
    const hasLifetimeRemaining = lifetimeRemaining !== null && lifetimeRemaining !== undefined;
    const showLifetimeInline = hasLifetimeRemaining && lifetimeRemaining > 10;
    const showLifetimeSeparate = hasLifetimeRemaining && lifetimeRemaining <= 10;
    const lifetimeWarning = hasLifetimeRemaining && lifetimeRemaining < 20;
    const lifetimeCritical = hasLifetimeRemaining && lifetimeRemaining <= 5;
    const lifetimeTooltip = !hasLifetimeRemaining
        ? ''
        : lifetimeRemaining <= 10
            ? this.t('tooltip_lifetime_remaining_critical')
            : lifetimeRemaining <= 20
                ? this.t('tooltip_lifetime_remaining_plan')
                : this.t('tooltip_lifetime_remaining');
    
    if (device.power_on_hours !== null && device.power_on_hours !== undefined) {
        // Use pre-formatted string from backend if available, otherwise format client-side
        const formattedTime = device.power_on_formatted || this.formatPowerOnHours(device.power_on_hours);
        metrics.push(`
            <div class="usage-metric">
                <div class="usage-label" title="${this.t('tooltip_power_on_hours')}">⏱ ${this.t('power_on_hours')}</div>
                <div class="usage-value">${formattedTime}</div>
            </div>
        `);
    }
    
    if (device.is_ssd && device.total_bytes_written !== null && device.total_bytes_written !== undefined) {
        const lifetimeLine = showLifetimeInline ? `
            <div class="usage-subvalue ${lifetimeWarning ? 'usage-warning' : ''}" title="${lifetimeTooltip}">
                ${lifetimeWarning ? '⚠️ ' : ''}${this.t('lifetime_remaining')}: ${lifetimeRemaining}%
            </div>
        ` : '';
        metrics.push(`
            <div class="usage-metric">
                <div class="usage-label" title="${this.t('tooltip_total_bytes_written')}">💾 ${this.t('total_bytes_written')}</div>
                <div class="usage-value">${this.formatBytes(device.total_bytes_written)}</div>
                ${lifetimeLine}
            </div>
        `);
    } else if (!device.is_ssd && device.power_cycle_count !== null && device.power_cycle_count !== undefined) {
        metrics.push(`
            <div class="usage-metric">
                <div class="usage-label" title="${this.t('tooltip_power_on_cycles')}">🔄 ${this.t('power_on_cycles')}</div>
                <div class="usage-value">${device.power_cycle_count.toLocaleString()}</div>
            </div>
        `);
    }

    if (showLifetimeSeparate) {
        const metricClass = lifetimeCritical ? 'usage-metric usage-metric-critical' : 'usage-metric usage-metric-warning';
        const valueClass = lifetimeCritical ? 'usage-critical' : 'usage-warning';
        const detailText = lifetimeCritical
            ? `
                <div class="usage-subvalue ${valueClass}">${this.t('lifetime_remaining_near_end')}</div>
                <div class="usage-subvalue ${valueClass}">${this.t('lifetime_remaining_replace_soon')}</div>
            `
            : `<div class="usage-subvalue ${valueClass}">${this.t('lifetime_remaining_near_end')}</div>`;
        metrics.push(`
            <div class="${metricClass}">
                <div class="usage-label" title="${lifetimeTooltip}">⌛ ${this.t('lifetime_remaining_label')}</div>
                <div class="usage-value ${valueClass}" title="${lifetimeTooltip}">⚠️ ${this.t('lifetime_remaining')}: ${lifetimeRemaining}%</div>
                ${detailText}
            </div>
        `);
    }
    
    if (metrics.length === 0) {
        return '';
    }
    
    return `
        <div class="usage-section">
            ${metrics.join('')}
        </div>
    `;
};

// ===== SECONDARY SMART ATTRIBUTES SECTION (Priority 6) =====
App.renderSecondaryAttributes = function(device) {
    if (!device.components) {
        return '';
    }
    
    const escalatedNames = (device.escalated_attributes || []).map(attr => attr.name);
    const attributes = [];
    
    if (!escalatedNames.includes('reallocated_sectors') && 
        device.components.reallocated?.value !== null && 
        device.components.reallocated?.value !== undefined) {
        attributes.push({
            key: 'reallocated_sectors',
            name: this.t('reallocated_sectors'),
            value: device.components.reallocated.value.toLocaleString(),
            icon: '🧱'
        });
    }
    
    if (!escalatedNames.includes('pending_sectors') && 
        device.components.pending?.value !== null && 
        device.components.pending?.value !== undefined) {
        attributes.push({
            key: 'pending_sectors',
            name: this.t('pending_sectors'),
            value: device.components.pending.value.toLocaleString(),
            icon: '⚠️'
        });
    }
    
    // Add mosmart188 if 1-5 errors (not escalated)
    if (!escalatedNames.includes('mosmart188') &&
        device.mosmart188?.count > 0 &&
        device.mosmart188?.count <= 5) {
        const errorReason = device.mosmart188?.last_error_reason;
        attributes.push({
            key: 'mosmart188',
            name: this.getAttributeDisplayName('mosmart188', errorReason),
            value: device.mosmart188.count.toLocaleString(),
            icon: '⚠️'
        });
    }
    
    if (attributes.length === 0) {
        return '';
    }
    
    const attrsHTML = attributes.map(attr => `
        <div class="secondary-attribute">
            <span class="secondary-icon">${attr.icon}</span>
            <span class="secondary-name" title="${this.getAttributeTooltip(attr.key)}">${attr.name}</span>
            <span class="secondary-value">${attr.value}</span>
        </div>
    `).join('');
    
    return `
        <div class="secondary-section">
            <div class="secondary-header">${this.t('smart_attributes')}</div>
            <div class="secondary-list">${attrsHTML}</div>
        </div>
    `;
};

// ===== DEVICE ACTIONS SECTION =====
App.renderDeviceActions = function(device) {
    return `
        <div class="device-actions">
            <button class="btn-info btn-view-history" data-device="${device.name}">
                📊 ${this.t('view_history')}
            </button>
            <button class="btn-secondary btn-view-log" data-device="${device.name}">
                📄 ${this.t('view_log')}
            </button>
            <button class="btn-secondary btn-print-label" data-device="${device.name}">
                🏷️ ${this.t('print_label')}
            </button>
        </div>
    `;
};

// ===== HELPER FUNCTIONS =====

App.getAttributeDisplayName = function(attrName, errorReason) {
    const nameMap = {
        'reallocated_sectors': this.t('reallocated_sectors'),
        'pending_sectors': this.t('pending_sectors'),
        'uncorrectable_errors': 'Uncorrectable Errors',
        'mosmart188': 'mosmart188 - Disk Read Error'
    };
    return nameMap[attrName] || attrName;
};

App.getAttributeTooltip = function(attrName, errorReason) {
    const tooltipMap = {
        'reallocated_sectors': this.t('tooltip_reallocated_sectors'),
        'pending_sectors': this.t('tooltip_pending_sectors'),
        'uncorrectable_errors': this.t('tooltip_uncorrectable_errors'),
        'mosmart188': this.t('tooltip_mosmart188')
    };
    return tooltipMap[attrName] || attrName;
};

App.getAttributeIcon = function(attrName) {
    const iconMap = {
        'reallocated_sectors': '🧱',
        'pending_sectors': '⚠️',
        'uncorrectable_errors': '❌',
        'mosmart188': '📡'
    };
    return iconMap[attrName] || '⚠️';
};

App.getTemperatureClass = function(temp, isSSD) {
    if (isSSD) {
        if (temp >= 75) return 'temp-critical';
        if (temp >= 60) return 'temp-warning';
    } else {
        if (temp >= 65) return 'temp-critical';
        if (temp >= 50) return 'temp-warning';
    }
    return 'temp-ok';
};

App.updateFilters = function() {
    const container = document.getElementById('device-filters');
    
    if (!this.state.devices || this.state.devices.length === 0) {
        container.innerHTML = '';
        return;
    }
    
    container.innerHTML = this.state.devices.map(device => `
        <div class="device-filter-chip ${this.state.selectedDevices.has(device.name) ? 'active' : ''}"
             onclick="App.toggleFilter('${device.name}')">
            ${device.name}
        </div>
    `).join('');
};

App.toggleFilter = function(deviceName) {
    if (this.state.selectedDevices.has(deviceName)) {
        this.state.selectedDevices.delete(deviceName);
    } else {
        this.state.selectedDevices.add(deviceName);
    }
    this.updateFilters();
    this.renderDevices();
};

App.selectAllDisks = function() {
    this.state.devices.forEach(d => this.state.selectedDevices.add(d.name));
    this.updateFilters();
    this.renderDevices();
};

App.deselectAllDisks = function() {
    this.state.selectedDevices.clear();
    this.updateFilters();
    this.renderDevices();
};

// ===== HELPER FUNCTIONS =====
App.getDeviceStatus = function(device) {
    const gdcState = device.gdc_state?.state || 'OK';
    
    // UNASSESSABLE: Missing SMART data is not disk failure. GDC is triggered by lying data, not missing data.
    if (gdcState === 'UNASSESSABLE') {
        return 'unassessable';
    }
    
    // GDC states: SUSPECT, CONFIRMED, TERMINAL
    if (gdcState && gdcState !== 'OK') {
        return 'gdc';
    }
    
    if (device.health_score === null || device.health_score === undefined) {
        return 'warning';
    }
    if (device.health_score < 20) {
        return 'critical';  // 0-19: KRITISK
    }
    if (device.health_score < 40) {
        return 'poor';  // 20-39: Dårlig
    }
    if (device.health_score < 60) {
        return 'warning';  // 40-59: Advarsel
    }
    if (device.health_score < 80) {
        return 'acceptable';  // 60-79: Akseptabel
    }
    if (device.health_score < 95) {
        return 'good';  // 80-94: God
    }
    
    // Excellent requires PERFECT disk: no defects at all
    const hasDefects = (device.components?.reallocated?.value > 0) || 
                      (device.components?.pending?.value > 0) || 
                      (device.components?.uncorrectable?.value > 0);
    
    if (hasDefects) {
        return 'good';  // 95-100 with defects: God (not Excellent)
    }
    
    return 'excellent';  // 95-100 with zero defects: UTMERKET
};

App.getHealthClass = function(score) {
    if (score === null || score === undefined) return 'warning';
    if (score < 40) return 'critical';
    if (score < 60) return 'warning';
    if (score < 80) return 'acceptable';
    if (score < 95) return 'good';
    return 'excellent';
};

App.formatBytes = function(bytes) {
    if (!bytes || bytes === 0) return 'N/A';
    const units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB'];
    let value = bytes;
    let unitIndex = 0;
    
    while (value >= 1024 && unitIndex < units.length - 1) {
        value /= 1024;
        unitIndex++;
    }
    
    return `${value.toFixed(1)} ${units[unitIndex]}`;
};

App.formatPowerOnHours = function(hours) {
    // Don't show N/A for 0 - it's valid (e.g., Power_On_Seconds with < 1 hour)
    if (hours === null || hours === undefined) return 'N/A';
    
    if (hours === 0) {
        return `0 ${App.t('time_hours')} (0 H)`;
    }
    
    const years = Math.floor(hours / 8760);
    const remainingAfterYears = hours % 8760;
    const days = Math.floor(remainingAfterYears / 24);
    const hoursLeft = remainingAfterYears % 24;
    
    const parts = [];
    if (years > 0) parts.push(`${years} ${App.t('time_years')}`);
    if (days > 0) parts.push(`${days} ${App.t('time_days')}`);
    if (hoursLeft > 0) parts.push(`${hoursLeft} ${App.t('time_hours')}`);
    
    return `${parts.join(', ')} (${hours} H)`;
};

App.updateLastUpdate = function() {
    const elem = document.getElementById('last-update');
    if (elem) {
        const now = new Date();
        const timeStr = now.toLocaleTimeString(this.config.language === 'no' ? 'nb-NO' : 'en-US');
        elem.textContent = `${this.t('last_updated') || 'Sist oppdatert'}: ${timeStr}`;
    }
};

App.startAutoRefresh = function() {
    if (this.state.autoRefreshTimer) {
        clearInterval(this.state.autoRefreshTimer);
    }
    
    const interval = this.config.refreshInterval * 1000;
    this.state.autoRefreshTimer = setInterval(() => {
        this.refreshData();
    }, interval);
    
    console.log(`Auto-refresh started: every ${this.config.refreshInterval}s`);
};

// ===== DEVICE ACTIONS =====
App.toggleMonitoring = async function(deviceName) {
    try {
        const response = await fetch(`/api/toggle/${deviceName}`, { method: 'POST' });
        
        if (!response.ok) {
            const text = await response.text();
            throw new Error('Failed to toggle monitoring: ' + text);
        }
        
        const result = await response.json();
        
        // Update local state immediately
        const device = this.state.devices.find(d => d.name === deviceName);
        if (device) {
            device.is_monitored = result.is_monitored;
        }
        
        // Force immediate re-render
        this.renderDevices();
        
        // Also refresh from server to ensure sync
        await this.refreshData();
        
    } catch (error) {
        console.error('Error toggling monitoring:', error);
        alert('Kunne ikke endre overvåking: ' + error.message);
    }
};

App.viewHistory = async function(deviceName, days = 7) {
    // Support both device name (string) and device object
    let device;
    if (typeof deviceName === 'string') {
        device = this.state.devices.find(d => d.name === deviceName);
        if (!device) {
            alert('Device not found');
            return;
        }
    } else {
        // deviceName is actually a device object
        device = deviceName;
        deviceName = device.name;
    }
    
    // Open modal
    const modal = document.getElementById('historyModal');
    const title = document.getElementById('history-title');
    const content = document.getElementById('history-content');
    
    // Add period selector to title
    title.innerHTML = `
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <span>${deviceName} - ${device.model || 'History'}</span>
            <div class="period-selector">
                <button class="btn-period ${days === 1 ? 'active' : ''}" data-days="1">${this.t('period_24h')}</button>
                <button class="btn-period ${days === 7 ? 'active' : ''}" data-days="7">${this.t('period_week')}</button>
                <button class="btn-period ${days === 30 ? 'active' : ''}" data-days="30">${this.t('period_month')}</button>
            </div>
        </div>
    `;
    
    // Add click handlers for period buttons
    title.querySelectorAll('.btn-period').forEach(btn => {
        btn.addEventListener('click', () => {
            const newDays = parseInt(btn.dataset.days);
            // Pass device object instead of deviceName to preserve functionality for disconnected disks
            this.viewHistory(device, newDays);
        });
    });
    
    // Show loading
    content.innerHTML = `
        <div class="loading-spinner">
            <div class="spinner"></div>
            <p>${this.t('loading_history')}</p>
        </div>
    `;
    
    modal.classList.add('active');
    
    try {
        // Fetch history from API
        const response = await fetch(`/api/history/${encodeURIComponent(device.model)}/${encodeURIComponent(device.serial)}?days=${days}`);
        if (!response.ok) throw new Error('Failed to load history');
        
        const data = await response.json();
        
        if (!data.history || data.history.length === 0) {
            content.innerHTML = `<p style="text-align: center; padding: 40px;">${this.t('no_history_available')}</p>`;
            return;
        }
        
        // Store history for toggle functionality
        this.state.currentHistory = data.history;
        this.state.currentDevice = deviceName;
        this.state.currentDays = days;
        
        // Get selected charts for this disk (or auto-select)
        const selectedCharts = this.getSelectedCharts(deviceName, data.history);
        
        // Render chart selector + charts
        content.innerHTML = `
            <div class="chart-selector">
                <div class="chart-selector-header">
                    <label class="auto-mode-toggle">
                        <input type="checkbox" 
                               ${selectedCharts.auto ? 'checked' : ''}
                               onchange="App.toggleAutoMode('${deviceName}', this.checked)">
                        <span>🤖 Automatisk graf-valg</span>
                    </label>
                    <span class="chart-hint">Velg inntil 2 grafer:</span>
                </div>
                <div class="chart-selector-options">
                    <label class="chart-option" data-disabled="${selectedCharts.auto}">
                        <input type="checkbox" value="mosmart188" 
                               ${selectedCharts.selected.includes('mosmart188') ? 'checked' : ''}
                               ${selectedCharts.auto ? 'disabled' : ''}
                               onchange="App.updateChartSelection('${deviceName}', this)">
                        <span>mosmart188 (disk restarts)</span>
                    </label>
                    <label class="chart-option" data-disabled="${selectedCharts.auto}">
                        <input type="checkbox" value="uncorrectable" 
                               ${selectedCharts.selected.includes('uncorrectable') ? 'checked' : ''}
                               ${selectedCharts.auto ? 'disabled' : ''}
                               onchange="App.updateChartSelection('${deviceName}', this)">
                        <span>Uncorrectable Sectors</span>
                    </label>
                    <label class="chart-option" data-disabled="${selectedCharts.auto}">
                        <input type="checkbox" value="reallocated" 
                               ${selectedCharts.selected.includes('reallocated') ? 'checked' : ''}
                               ${selectedCharts.auto ? 'disabled' : ''}
                               onchange="App.updateChartSelection('${deviceName}', this)">
                        <span>Reallocated Sectors</span>
                    </label>
                    <label class="chart-option" data-disabled="${selectedCharts.auto}">
                        <input type="checkbox" value="pending" 
                               ${selectedCharts.selected.includes('pending') ? 'checked' : ''}
                               ${selectedCharts.auto ? 'disabled' : ''}
                               onchange="App.updateChartSelection('${deviceName}', this)">
                        <span>Pending Sectors</span>
                    </label>
                </div>
            </div>
            
            <div class="charts-grid">
                <div class="chart-container">
                    <div class="chart-title">${this.t('health_score')} Trend</div>
                    <canvas id="health-chart"></canvas>
                </div>
                <div class="chart-container">
                    <div class="chart-title">${this.t('temperature')} Trend</div>
                    <canvas id="temp-chart"></canvas>
                </div>
                ${selectedCharts.selected.map(chart => `
                    <div class="chart-container">
                        <div class="chart-title">${this.getChartTitle(chart)} Trend</div>
                        <canvas id="${chart}-chart"></canvas>
                    </div>
                `).join('')}
            </div>
        `;
        
        // Draw charts
        setTimeout(() => {
            this.drawHistoryCharts(data.history, days, deviceName, selectedCharts.selected);
        }, 100);
        
    } catch (error) {
        console.error('Error loading history:', error);
        content.innerHTML = `<p style="text-align: center; padding: 40px; color: var(--status-critical);">${this.t('could_not_load_history')}</p>`;
    }
};

// ===== CHART SELECTION LOGIC =====

App.getChartTitle = function(chartType) {
    const titles = {
        'mosmart188': 'mosmart188 (Disk Restarts)',
        'uncorrectable': 'Uncorrectable Sectors',
        'reallocated': 'Reallocated Sectors',
        'pending': 'Pending Sectors'
    };
    return titles[chartType] || chartType;
};

App.getSelectedCharts = function(deviceName, history) {
    // Load from localStorage (per disk)
    const storageKey = `mosmart_charts_${deviceName}`;
    const stored = localStorage.getItem(storageKey);
    
    if (stored) {
        const parsed = JSON.parse(stored);
        if (parsed.auto) {
            // Auto mode: recalculate selection
            return {
                auto: true,
                selected: this.autoCalculateCharts(history)
            };
        } else {
            // Manual mode: use stored selection
            return {
                auto: false,
                selected: parsed.selected || []
            };
        }
    }
    
    // Default: auto mode
    return {
        auto: true,
        selected: this.autoCalculateCharts(history)
    };
};

App.autoCalculateCharts = function(history) {
    if (!history || history.length < 2) return ['reallocated', 'pending'];
    
    // Get latest and previous record
    const latest = history[history.length - 1];
    const previous = history[history.length - 2];
    
    // Define priority and check if active
    const charts = [
        {
            name: 'mosmart188',
            priority: 1,
            active: this.isChartActive('mosmart188', latest),
            change: this.getAbsoluteChange('mosmart188', latest, previous)
        },
        {
            name: 'uncorrectable',
            priority: 1,
            active: this.isChartActive('uncorrectable', latest),
            change: this.getAbsoluteChange('uncorrectable', latest, previous)
        },
        {
            name: 'reallocated',
            priority: 2,
            active: this.isChartActive('reallocated', latest),
            change: this.getAbsoluteChange('reallocated', latest, previous)
        },
        {
            name: 'pending',
            priority: 3,
            active: this.isChartActive('pending', latest),
            change: this.getAbsoluteChange('pending', latest, previous)
        }
    ];
    
    // Filter to active only
    const activeCharts = charts.filter(c => c.active);
    
    if (activeCharts.length === 0) {
        // No active charts: fallback to reallocated + pending
        return ['reallocated', 'pending'];
    }
    
    // Sort by priority (lower = higher priority), then by change rate
    activeCharts.sort((a, b) => {
        if (a.priority !== b.priority) return a.priority - b.priority;
        return b.change - a.change;  // Descending change
    });
    
    // Take top 2
    return activeCharts.slice(0, 2).map(c => c.name);
};

App.isChartActive = function(chartType, record) {
    if (chartType === 'mosmart188') {
        const mosmart = record.components?.mosmart188;
        if (!mosmart) return false;
        // Active if restart_count > 0 OR score < 100
        return (mosmart.value > 0) || (mosmart.score < 100);
    }
    
    const value = record.components?.[chartType]?.value;
    return value != null && value > 0;
};

App.getAbsoluteChange = function(chartType, latest, previous) {
    let latestValue, previousValue;
    
    if (chartType === 'mosmart188') {
        latestValue = latest.components?.mosmart188?.value || 0;
        previousValue = previous.components?.mosmart188?.value || 0;
    } else {
        latestValue = latest.components?.[chartType]?.value || 0;
        previousValue = previous.components?.[chartType]?.value || 0;
    }
    
    return Math.abs(latestValue - previousValue);
};

App.toggleAutoMode = function(deviceName, isAuto) {
    const storageKey = `mosmart_charts_${deviceName}`;
    
    if (isAuto) {
        // Switch to auto mode
        localStorage.setItem(storageKey, JSON.stringify({ auto: true }));
    } else {
        // Switch to manual mode with current auto-selected charts
        const autoCharts = this.state.currentHistory 
            ? this.autoCalculateCharts(this.state.currentHistory) 
            : ['reallocated', 'pending'];
        localStorage.setItem(storageKey, JSON.stringify({ 
            auto: false, 
            selected: autoCharts 
        }));
    }
    
    // Refresh chart view immediately
    if (this.state.currentDevice === deviceName && this.state.currentDays) {
        this.refreshChartView(deviceName, this.state.currentDays);
    }
};

App.updateChartSelection = function(deviceName, checkbox) {
    const storageKey = `mosmart_charts_${deviceName}`;
    
    // Get all checkboxes (skip auto-mode checkbox)
    const checkboxes = document.querySelectorAll('.chart-selector-options input[type="checkbox"]');
    let selected = [];
    checkboxes.forEach(cb => {
        if (cb.checked && cb.value) selected.push(cb.value);
    });
    
    // Enforce max 2 selections
    if (selected.length > 2) {
        checkbox.checked = false;
        alert('Maksimalt 2 grafer kan velges (i tillegg til Helse og Temperatur)');
        return;
    }
    
    // Save selection (manual mode)
    localStorage.setItem(storageKey, JSON.stringify({
        auto: false,
        selected: selected
    }));
    
    // Refresh chart view immediately
    if (this.state.currentDevice === deviceName && this.state.currentDays) {
        this.refreshChartView(deviceName, this.state.currentDays);
    }
};

// ===== CHART DRAWING =====

App.drawHistoryCharts = function(history, days, deviceName, selectedCharts) {
    if (!history || history.length === 0) return;
    
    // Destroy ALL existing charts before creating new ones
    Object.keys(this.charts).forEach(key => {
        if (this.charts[key]) this.charts[key].destroy();
    });
    this.charts = {};
    
    // Filter by actual time period, not just point count
    const now = new Date();
    const cutoffTime = new Date(now.getTime() - (days * 24 * 60 * 60 * 1000));
    
    let records = history.filter(h => {
        const recordTime = new Date(h.timestamp);
        return recordTime >= cutoffTime;
    });
    
    // If no records in period, show message
    if (records.length === 0) {
        const msgKey = days === 1 ? 'no_log_data_24h' : days === 7 ? 'no_log_data_week' : 'no_log_data_month';
        document.getElementById('history-content').innerHTML = `
            <div style="text-align: center; padding: 40px;">
                <p>${this.t(msgKey)}</p>
            </div>
        `;
        return;
    }
    
    // Smart downsampling: select representative points
    let sampledRecords = records;
    if (days === 1) {
        // 24h: Every ~90 minutes (aim for 16 points)
        const step = Math.max(1, Math.floor(records.length / 16));
        sampledRecords = records.filter((_, i) => i % step === 0 || i === records.length - 1);
    } else if (days === 7) {
        // Week: 2 per day, morning (~6-12h) and evening (~18-23h)
        const byDay = {};
        records.forEach(r => {
            const date = new Date(r.timestamp);
            const day = date.toDateString();
            const hour = date.getHours();
            if (!byDay[day]) byDay[day] = { morning: null, evening: null };
            
            if (hour >= 6 && hour < 12 && !byDay[day].morning) {
                byDay[day].morning = r;
            } else if (hour >= 18 && hour < 24 && !byDay[day].evening) {
                byDay[day].evening = r;
            } else if (!byDay[day].morning && !byDay[day].evening) {
                // Fallback: use any point if no morning/evening found yet
                byDay[day].morning = r;
            }
        });
        sampledRecords = [];
        Object.values(byDay).forEach(day => {
            if (day.morning) sampledRecords.push(day.morning);
            if (day.evening) sampledRecords.push(day.evening);
        });
        sampledRecords.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
    } else if (days === 30) {
        // Month: Every other day (aim for 15 points)
        const byDay = {};
        records.forEach(r => {
            const day = new Date(r.timestamp).toDateString();
            if (!byDay[day]) byDay[day] = [];
            byDay[day].push(r);
        });
        const days_list = Object.keys(byDay).sort((a, b) => new Date(a) - new Date(b));
        sampledRecords = [];
        days_list.forEach((day, i) => {
            if (i % 2 === 0 || i === days_list.length - 1) {
                // Take middle point of the day
                const dayRecords = byDay[day];
                sampledRecords.push(dayRecords[Math.floor(dayRecords.length / 2)]);
            }
        });
    }
    
    // Smart date formatting based on time period
    const labels = sampledRecords.map((h, i) => {
        const date = new Date(h.timestamp);
        const today = new Date().toDateString();
        const dateStr = date.toDateString();
        
        // If today, show only time
        if (dateStr === today) {
            return date.toLocaleTimeString('nb-NO', { hour: '2-digit', minute: '2-digit' });
        }
        
        // If multiple sampled records same day, show date + time
        const sameDay = sampledRecords.filter(r => new Date(r.timestamp).toDateString() === dateStr).length;
        if (sameDay > 1) {
            // Multiple records same day: show date + time
            return date.toLocaleDateString('nb-NO', { month: 'short', day: 'numeric' }) + ' ' + 
                   date.toLocaleTimeString('nb-NO', { hour: '2-digit', minute: '2-digit' });
        }
        
        // Single record for this day: show only date
        return date.toLocaleDateString('nb-NO', { month: 'short', day: 'numeric' });
    });
    
    const healthData = sampledRecords.map(h => h.health_score);
    const tempData = sampledRecords.map(h => h.components?.temperature?.value || null);
    // Missing SMART data is not disk failure. GDC is triggered by lying data, not missing data.
    // Represent missing data as null (graph breaks), not 0 (misleading)
    const reallocatedData = sampledRecords.map(h => h.components?.reallocated?.value ?? null);
    const pendingData = sampledRecords.map(h => h.components?.pending?.value ?? null);
    const uncorrectableData = sampledRecords.map(h => h.components?.uncorrectable?.value ?? null);
    const mosmart188Data = sampledRecords.map(h => h.components?.mosmart188?.value ?? null);
    
    // Health chart
    const healthCtx = document.getElementById('health-chart');
    if (healthCtx) {
        this.charts.health = new Chart(healthCtx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Health Score',
                    data: healthData,
                    borderColor: '#278cff',
                    backgroundColor: 'rgba(39, 140, 255, 0.1)',
                    fill: true,
                    tension: 0.4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false }
                },
                scales: {
                    y: {
                        beginAtZero: false,
                        min: 0,
                        max: 100
                    }
                }
            }
        });
    }
    
    // Temperature chart
    const tempCtx = document.getElementById('temp-chart');
    if (tempCtx) {
        this.charts.temp = new Chart(tempCtx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Temperature (°C)',
                    data: tempData,
                    borderColor: '#fbbf24',
                    backgroundColor: 'rgba(251, 191, 36, 0.1)',
                    fill: true,
                    tension: 0.4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false }
                }
            }
        });
    }
    
    // Dynamic charts based on selection
    if (selectedCharts && selectedCharts.length > 0) {
        selectedCharts.forEach(chartType => {
            const ctx = document.getElementById(`${chartType}-chart`);
            if (!ctx) return;
            
            let data, color, bgColor, label;
            
            switch(chartType) {
                case 'reallocated':
                    data = reallocatedData;
                    color = '#f85149';
                    bgColor = 'rgba(248, 81, 73, 0.1)';
                    label = 'Reallocated Sectors';
                    break;
                case 'pending':
                    data = pendingData;
                    color = '#d29922';
                    bgColor = 'rgba(210, 153, 34, 0.1)';
                    label = 'Pending Sectors';
                    break;
                case 'uncorrectable':
                    data = uncorrectableData;
                    color = '#da3633';
                    bgColor = 'rgba(218, 54, 51, 0.1)';
                    label = 'Uncorrectable Sectors';
                    break;
                case 'mosmart188':
                    data = mosmart188Data;
                    color = '#8250df';
                    bgColor = 'rgba(130, 80, 223, 0.1)';
                    label = 'mosmart188 (Restarts 24h)';
                    break;
                default:
                    return;
            }
            
            this.charts[chartType] = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [{
                        label: label,
                        data: data,
                        borderColor: color,
                        backgroundColor: bgColor,
                        fill: true,
                        tension: 0.4,
                        stepped: true,
                        spanGaps: false  // Break graph at null values (missing data)
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false }
                    },
                    scales: {
                        y: {
                            beginAtZero: true
                        }
                    }
                }
            });
        });
    }
};

// Helper function to re-render charts without fetching data
App.refreshChartView = function(deviceName, days) {
    const content = document.getElementById('history-content');
    if (!content || !this.state.currentHistory) return;
    
    const data = { history: this.state.currentHistory };
    const selectedCharts = this.getSelectedCharts(deviceName, data.history);
    
    // Re-render chart selector + charts
    content.innerHTML = `
        <div class="chart-selector">
            <div class="chart-selector-header">
                <label class="auto-mode-toggle">
                    <input type="checkbox" 
                           ${selectedCharts.auto ? 'checked' : ''}
                           onchange="App.toggleAutoMode('${deviceName}', this.checked)">
                    <span>🤖 Automatisk graf-valg</span>
                </label>
                <span class="chart-hint">Velg inntil 2 grafer:</span>
            </div>
            <div class="chart-selector-options">
                <label class="chart-option" data-disabled="${selectedCharts.auto}">
                    <input type="checkbox" value="mosmart188" 
                           ${selectedCharts.selected.includes('mosmart188') ? 'checked' : ''}
                           ${selectedCharts.auto ? 'disabled' : ''}
                           onchange="App.updateChartSelection('${deviceName}', this)">
                    <span>mosmart188 (disk restarts)</span>
                </label>
                <label class="chart-option" data-disabled="${selectedCharts.auto}">
                    <input type="checkbox" value="uncorrectable" 
                           ${selectedCharts.selected.includes('uncorrectable') ? 'checked' : ''}
                           ${selectedCharts.auto ? 'disabled' : ''}
                           onchange="App.updateChartSelection('${deviceName}', this)">
                    <span>Uncorrectable Sectors</span>
                </label>
                <label class="chart-option" data-disabled="${selectedCharts.auto}">
                    <input type="checkbox" value="reallocated" 
                           ${selectedCharts.selected.includes('reallocated') ? 'checked' : ''}
                           ${selectedCharts.auto ? 'disabled' : ''}
                           onchange="App.updateChartSelection('${deviceName}', this)">
                    <span>Reallocated Sectors</span>
                </label>
                <label class="chart-option" data-disabled="${selectedCharts.auto}">
                    <input type="checkbox" value="pending" 
                           ${selectedCharts.selected.includes('pending') ? 'checked' : ''}
                           ${selectedCharts.auto ? 'disabled' : ''}
                           onchange="App.updateChartSelection('${deviceName}', this)">
                    <span>Pending Sectors</span>
                </label>
            </div>
        </div>
        
        <div class="charts-grid">
            <div class="chart-container">
                <div class="chart-title">${this.t('health_score')} Trend</div>
                <canvas id="health-chart"></canvas>
            </div>
            <div class="chart-container">
                <div class="chart-title">${this.t('temperature')} Trend</div>
                <canvas id="temp-chart"></canvas>
            </div>
            ${selectedCharts.selected.map(chart => `
                <div class="chart-container">
                    <div class="chart-title">${this.getChartTitle(chart)} Trend</div>
                    <canvas id="${chart}-chart"></canvas>
                </div>
            `).join('')}
        </div>
    `;
    
    // Re-draw charts
    setTimeout(() => {
        this.drawHistoryCharts(data.history, days, deviceName, selectedCharts.selected);
    }, 100);
};

App.closeHistory = function() {
    document.getElementById('historyModal').classList.remove('active');
};

App.viewLog = async function(deviceName) {
    // Support both device name (string) and device object
    let device;
    if (typeof deviceName === 'string') {
        device = this.state.devices.find(d => d.name === deviceName);
        if (!device) {
            alert('Device not found');
            return;
        }
    } else {
        // deviceName is actually a device object
        device = deviceName;
        deviceName = device.name;
    }
    
    // Check if device has model and serial (GDC devices may not have these)
    if (!device.model || !device.serial) {
        alert(this.t('no_log_file'));
        return;
    }
    
    try {
        const response = await fetch(`/api/logs/${encodeURIComponent(device.model)}/${encodeURIComponent(device.serial)}`);
        if (!response.ok) {
            alert(this.t('no_log_found'));
            return;
        }
        
        const data = await response.json();
        
        if (!data.entries || data.entries.length === 0) {
            alert(this.t('could_not_load_log'));
            return;
        }
        
        // Create a formatted text view
        let logText = `=== LOGGFIL FOR ${device.name} (${device.model}) ===\n`;
        logText += `Serial: ${device.serial}\n`;
        logText += `Totalt ${data.log_count} oppføringer (viser siste 100)\n`;
        logText += `\n${'='.repeat(80)}\n\n`;
        
        data.entries.reverse().forEach(entry => {
            const date = new Date(entry.timestamp);
            logText += `Tidspunkt: ${date.toLocaleString('nb-NO')}\n`;
            
            // Check if this is a USB event
            if (entry.is_usb_event && entry.event_type) {
                const eventIcon = entry.event_type === 'usb_connected' ? '🔌 ✅' : '🔌 ❌';
                const eventText = entry.event_type === 'usb_connected' ? 'USB TILKOBLET' : 'USB FRAKOBLET';
                logText += `${eventIcon} ${eventText}\n`;
                logText += `Enhet: ${entry.device_name}\n`;
                logText += `Melding: ${entry.message}\n`;
            } else if (entry.is_system_event && entry.event_type === 'system_uncontrolled_shutdown') {
                logText += `\n⚠️  SYSTEMHENDELSE\n`;
                logText += `━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n`;
                logText += `${entry.message || 'Ukontrollert avslutning oppdaget'}\n`;
                if (entry.affected_disks_count !== undefined) {
                    logText += `Påvirket disker: ${entry.affected_disks_count}\n`;
                }
                if (entry.note) {
                    logText += `${entry.note}\n`;
                }
                logText += `━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n`;
            } else if (entry.is_gdc_event) {
                // GDC event entry
                logText += `\n⚠️  GHOST DRIVE CONDITION (GDC) EVENT\n`;
                logText += `━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n`;
                logText += `${entry.message || entry.user_message || 'GDC state change'}\n`;
                if (entry.old_state && entry.new_state) {
                    logText += `Status: ${entry.old_state} → ${entry.new_state}\n`;
                }
                logText += `━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n`;
            } else {
                // Normal SMART log entry
                logText += `Health Score: ${entry.health_score}\n`;
                logText += `Temperatur: ${entry.temperature}°C\n`;
                logText += `Assessment: ${entry.assessment}\n`;
                
                if (entry.components) {
                    logText += `Komponenter:\n`;
                    Object.entries(entry.components).forEach(([name, data]) => {
                        logText += `  - ${name}: ${data.value} (score: ${data.score})\n`;
                    });
                }
            }
            
            logText += `\n${'-'.repeat(80)}\n\n`;
        });
        
        // Open in new window
        const newWindow = window.open('', '_blank');
        newWindow.document.write(`
            <html>
            <head>
                <title>Loggfil - ${device.name}</title>
                <style>
                    body {
                        font-family: 'Courier New', monospace;
                        background-color: #0d1117;
                        color: #c9d1d9;
                        padding: 20px;
                        margin: 0;
                    }
                    pre {
                        white-space: pre-wrap;
                        word-wrap: break-word;
                    }
                    .log-header {
                        position: sticky;
                        top: 0;
                        background-color: #0d1117;
                        padding: 10px 0;
                        border-bottom: 2px solid #30363d;
                        margin-bottom: 20px;
                        display: flex;
                        gap: 10px;
                    }
                    .btn {
                        padding: 8px 16px;
                        background: #238636;
                        color: white;
                        border: none;
                        border-radius: 6px;
                        cursor: pointer;
                        font-size: 14px;
                    }
                    .btn:hover {
                        background: #2ea043;
                    }
                    .btn-secondary {
                        background: #21262d;
                    }
                    .btn-secondary:hover {
                        background: #30363d;
                    }
                    @media print {
                        .log-header {
                            display: none;
                        }
                        body {
                            background: white;
                            color: black;
                        }
                    }
                </style>
            </head>
            <body>
                <div class="log-header">
                    <button class="btn" onclick="window.print()">🖨️ ${this.t('print_button')}</button>
                    <button class="btn btn-secondary" onclick="downloadLog()">💾 ${this.t('download_txt_last100')}</button>
                    <button class="btn btn-secondary" onclick="downloadFullLog()">💾 ${this.t('download_full_log')}</button>
                </div>
                <pre id="logContent">${logText}</pre>
                <script>
                    function downloadLog() {
                        const content = document.getElementById('logContent').textContent;
                        const blob = new Blob([content], { type: 'text/plain' });
                        const url = URL.createObjectURL(blob);
                        const a = document.createElement('a');
                        a.href = url;
                        a.download = 'mosmart_log_${device.name}_${device.model}_${new Date().toISOString().split('T')[0]}.txt';
                        a.click();
                        URL.revokeObjectURL(url);
                    }
                    
                    async function downloadFullLog() {
                        if (!confirm('${this.t('download_full_warning')}')) {
                            return;
                        }
                        
                        try {
                            const response = await fetch('/api/logs-full/${encodeURIComponent(device.model)}/${encodeURIComponent(device.serial)}');
                            if (!response.ok) throw new Error('Failed to fetch full log');
                            
                            const data = await response.json();
                            
                            let fullLogText = '=== FULLSTENDIG LOGGFIL FOR ${device.name} (${device.model}) ===\\n';
                            fullLogText += 'Serial: ${device.serial}\\n';
                            fullLogText += 'Totalt ' + data.log_count + ' oppføringer\\n';
                            fullLogText += '\\n' + '='.repeat(80) + '\\n\\n';
                            
                            data.entries.reverse().forEach(entry => {
                                const date = new Date(entry.timestamp);
                                fullLogText += 'Tidspunkt: ' + date.toLocaleString('nb-NO') + '\\n';
                                
                                // Check if this is a USB event
                                if (entry.is_usb_event && entry.event_type) {
                                    const eventIcon = entry.event_type === 'usb_connected' ? '🔌 ✅' : '🔌 ❌';
                                    const eventText = entry.event_type === 'usb_connected' ? 'USB TILKOBLET' : 'USB FRAKOBLET';
                                    fullLogText += eventIcon + ' ' + eventText + '\\n';
                                    fullLogText += 'Enhet: ' + entry.device_name + '\\n';
                                    fullLogText += 'Melding: ' + entry.message + '\\n';
                                } else if (entry.is_system_event && entry.event_type === 'system_uncontrolled_shutdown') {
                                    fullLogText += '\n⚠️  SYSTEMHENDELSE\n';
                                    fullLogText += '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n';
                                    fullLogText += (entry.message || 'Ukontrollert avslutning oppdaget') + '\n';
                                    if (entry.affected_disks_count !== undefined) {
                                        fullLogText += 'Påvirket disker: ' + entry.affected_disks_count + '\n';
                                    }
                                    if (entry.note) {
                                        fullLogText += entry.note + '\n';
                                    }
                                    fullLogText += '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n';
                                } else if (entry.is_gdc_event) {
                                    // GDC event entry
                                    fullLogText += '\\n⚠️  GHOST DRIVE CONDITION (GDC) EVENT\\n';
                                    fullLogText += '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\\n';
                                    fullLogText += (entry.message || entry.user_message || 'GDC state change') + '\\n';
                                    if (entry.old_state && entry.new_state) {
                                        fullLogText += 'Status: ' + entry.old_state + ' → ' + entry.new_state + '\\n';
                                    }
                                    fullLogText += '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\\n';
                                } else {
                                    // Normal SMART log entry
                                    fullLogText += 'Health Score: ' + entry.health_score + '\\n';
                                    fullLogText += 'Temperatur: ' + entry.temperature + '°C\\n';
                                    fullLogText += 'Assessment: ' + entry.assessment + '\\n';
                                    
                                    if (entry.components) {
                                        fullLogText += 'Komponenter:\\n';
                                        Object.entries(entry.components).forEach(([name, data]) => {
                                            fullLogText += '  - ' + name + ': ' + data.value + ' (score: ' + data.score + ')\\n';
                                        });
                                    }
                                }
                                
                                fullLogText += '\\n' + '-'.repeat(80) + '\\n\\n';
                            });
                            
                            const blob = new Blob([fullLogText], { type: 'text/plain' });
                            const url = URL.createObjectURL(blob);
                            const a = document.createElement('a');
                            a.href = url;
                            a.download = 'mosmart_log_FULL_${device.name}_${device.model}_${new Date().toISOString().split('T')[0]}.txt';
                            a.click();
                            URL.revokeObjectURL(url);
                        } catch (error) {
                            alert('${this.t('could_not_load_full_log')}: ' + error.message);
                        }
                    }
                </script>
            </body>
            </html>
        `);
        newWindow.document.close();
        
    } catch (error) {
        console.error('Error loading log:', error);
        alert(this.t('could_not_load_log'));
    }
};

// ===== SETTINGS MODAL =====
App.openSettings = function() {
    if (!this.state.settings) {
        alert('Settings not loaded yet');
        return;
    }
    
    // Populate form
    this.populateSettingsForm();
    
    // Open modal
    document.getElementById('settingsModal').classList.add('active');
};

App.openSettingsSecurity = function() {
    if (!this.state.settings) {
        alert('Settings not loaded yet');
        return;
    }
    
    // Populate form
    this.populateSettingsForm();
    
    // Open modal and switch to security tab
    document.getElementById('settingsModal').classList.add('active');
    this.switchTab('security');
};

App.closeSettings = function() {
    document.getElementById('settingsModal').classList.remove('active');
};

App.switchTab = function(tabName) {
    // Update buttons
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.tab === tabName);
    });
    
    // Update content
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.toggle('active', content.id === `tab-${tabName}`);
    });
};

App.populateSettingsForm = function() {
    const s = this.state.settings;
    
    // General - populate language dropdown dynamically
    const langSelect = document.getElementById('setting-language');
    langSelect.innerHTML = this.availableLanguages.map(lang => 
        `<option value="${lang.code}">${lang.flag ? lang.flag + ' ' : ''}${lang.name}</option>`
    ).join('');
    langSelect.value = s.general?.language || 'no';
    
    // Add change event to reload language
    langSelect.addEventListener('change', async (e) => {
        await this.changeLanguage(e.target.value);
    });
    
    document.getElementById('setting-polling-interval').value = s.general?.polling_interval || 60;
    
    // Disks
    const diskList = document.getElementById('disk-selection-list');
    diskList.innerHTML = this.state.devices.map(device => `
        <div class="disk-item">
            <label>
                <input type="checkbox" 
                       id="disk-${device.name}" 
                       ${s.disk_selection?.monitored_devices?.[device.name] !== false ? 'checked' : ''}>
                ${device.name} - ${device.model || 'Unknown'}
            </label>
        </div>
    `).join('');
    
    document.getElementById('setting-ignore-usb').checked = s.disk_selection?.ignore_removable_usb || false;
    
    // Health
    document.getElementById('setting-score-drop').value = s.health_alerts?.score_drop_threshold || 3;
    document.getElementById('setting-critical-score').value = s.health_alerts?.critical_score_limit || 40;
    
    // SMART
    document.getElementById('setting-reallocated').value = (s.smart_alerts?.reallocated_milestones || []).join(',');
    document.getElementById('setting-pending').value = (s.smart_alerts?.pending_milestones || []).join(',');
    document.getElementById('setting-uncorrectable').value = s.smart_alerts?.uncorrectable_threshold || 1;
    document.getElementById('setting-timeout').value = s.smart_alerts?.timeout_threshold || 5;
    
    // Temperature
    document.getElementById('setting-ssd-warn').value = s.temperature_alerts?.ssd_warning || 60;
    document.getElementById('setting-ssd-crit').value = s.temperature_alerts?.ssd_critical || 70;
    document.getElementById('setting-hdd-warn').value = s.temperature_alerts?.hdd_warning || 50;
    document.getElementById('setting-hdd-crit').value = s.temperature_alerts?.hdd_critical || 60;
    document.getElementById('setting-consecutive').value = s.temperature_alerts?.consecutive_readings || 4;
    document.getElementById('setting-normalize-alert').checked = s.temperature_alerts?.alert_on_normalize || false;
    
    // GDC
    document.getElementById('setting-gdc-enabled').checked = s.gdc?.enabled !== false;
    document.getElementById('setting-gdc-threshold').value = s.gdc?.failed_polls_threshold || 5;
    
    // Emergency Unmount
    const emergencyMode = s.emergency_unmount?.mode || 'PASSIVE';
    document.getElementById('setting-emergency-unmount-active').checked = emergencyMode === 'ACTIVE';
    this.updateEmergencyUnmountStatus(emergencyMode);
    
    // Add change listener to update status indicator
    document.getElementById('setting-emergency-unmount-active').addEventListener('change', (e) => {
        const mode = e.target.checked ? 'ACTIVE' : 'PASSIVE';
        this.updateEmergencyUnmountStatus(mode);
    });
    
    // Logging
    document.getElementById('setting-log-retention').value = s.logging?.retention_size_kb || 1024;
    document.getElementById('setting-rolling-logs').checked = s.logging?.rolling_logs !== false;
    document.getElementById('setting-verbosity').value = s.logging?.verbosity || 'info';
    
    // Email
    const email = s.alert_channels?.email || {};
    document.getElementById('setting-email-enabled').checked = email.enabled || false;
    document.getElementById('setting-email-server').value = email.smtp_server || 'smtp.gmail.com';
    document.getElementById('setting-email-port').value = email.smtp_port || 587;
    document.getElementById('setting-email-tls').checked = email.use_tls !== false;
    document.getElementById('setting-email-starttls').checked = email.use_starttls !== false;
    document.getElementById('setting-email-user').value = email.smtp_username || '';
    document.getElementById('setting-email-pass').value = ''; // Never populate password
    document.getElementById('setting-email-from').value = email.from_email || '';
    document.getElementById('setting-email-to').value = (email.to_emails || []).join('\n');
    
    const severity = email.alert_on_severity || ['critical', 'high'];
    document.getElementById('setting-email-info').checked = severity.includes('info');
    document.getElementById('setting-email-warning').checked = severity.includes('warning');
    document.getElementById('setting-email-high').checked = severity.includes('high');
    document.getElementById('setting-email-critical').checked = severity.includes('critical');
};

App.saveSettings = async function() {
    const newSettings = {
        general: {
            language: document.getElementById('setting-language').value,
            polling_interval: parseInt(document.getElementById('setting-polling-interval').value),
            temperature_unit: 'C'
        },
        disk_selection: {
            monitored_devices: {},
            ignore_removable_usb: document.getElementById('setting-ignore-usb').checked
        },
        health_alerts: {
            score_drop_threshold: parseInt(document.getElementById('setting-score-drop').value),
            critical_score_limit: parseInt(document.getElementById('setting-critical-score').value)
        },
        smart_alerts: {
            reallocated_milestones: document.getElementById('setting-reallocated').value.split(',').map(v => parseInt(v.trim())),
            pending_milestones: document.getElementById('setting-pending').value.split(',').map(v => parseInt(v.trim())),
            uncorrectable_threshold: parseInt(document.getElementById('setting-uncorrectable').value),
            timeout_threshold: parseInt(document.getElementById('setting-timeout').value)
        },
        temperature_alerts: {
            ssd_warning: parseInt(document.getElementById('setting-ssd-warn').value),
            ssd_critical: parseInt(document.getElementById('setting-ssd-crit').value),
            hdd_warning: parseInt(document.getElementById('setting-hdd-warn').value),
            hdd_critical: parseInt(document.getElementById('setting-hdd-crit').value),
            consecutive_readings: parseInt(document.getElementById('setting-consecutive').value),
            alert_on_normalize: document.getElementById('setting-normalize-alert').checked
        },
        gdc: {
            enabled: document.getElementById('setting-gdc-enabled').checked,
            failed_polls_threshold: parseInt(document.getElementById('setting-gdc-threshold').value)
        },
        emergency_unmount: {
            mode: document.getElementById('setting-emergency-unmount-active').checked ? 'ACTIVE' : 'PASSIVE',
            require_confirmation: true
        },
        logging: {
            retention_size_kb: parseInt(document.getElementById('setting-log-retention').value),
            rolling_logs: document.getElementById('setting-rolling-logs').checked,
            verbosity: document.getElementById('setting-verbosity').value
        },
        alert_channels: {
            email: {
                enabled: document.getElementById('setting-email-enabled').checked,
                smtp_server: document.getElementById('setting-email-server').value,
                smtp_port: parseInt(document.getElementById('setting-email-port').value),
                use_tls: document.getElementById('setting-email-tls').checked,
                use_starttls: document.getElementById('setting-email-starttls').checked,
                smtp_username: document.getElementById('setting-email-user').value,
                from_email: document.getElementById('setting-email-from').value,
                to_emails: document.getElementById('setting-email-to').value.split('\n').filter(e => e.trim()),
                alert_on_severity: []
            }
        }
    };
    
    // Disk monitoring
    this.state.devices.forEach(device => {
        const checkbox = document.getElementById(`disk-${device.name}`);
        if (checkbox) {
            newSettings.disk_selection.monitored_devices[device.name] = checkbox.checked;
        }
    });
    
    // Email severity
    if (document.getElementById('setting-email-info').checked) newSettings.alert_channels.email.alert_on_severity.push('info');
    if (document.getElementById('setting-email-warning').checked) newSettings.alert_channels.email.alert_on_severity.push('warning');
    if (document.getElementById('setting-email-high').checked) newSettings.alert_channels.email.alert_on_severity.push('high');
    if (document.getElementById('setting-email-critical').checked) newSettings.alert_channels.email.alert_on_severity.push('critical');
    
    // Handle password - only include if user entered a new one
    const password = document.getElementById('setting-email-pass').value;
    if (password) {
        newSettings.alert_channels.email.smtp_password = password;
    } else {
        // Preserve existing encrypted password
        newSettings.alert_channels.email.smtp_password = this.state.settings.alert_channels?.email?.smtp_password || '';
    }
    
    try {
        const response = await fetch('/api/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(newSettings)
        });
        
        if (!response.ok) throw new Error('Failed to save settings');
        
        alert('Settings saved successfully!');
        
        // Update local state
        this.state.settings = newSettings;
        this.config.refreshInterval = newSettings.general.polling_interval;
        this.config.language = newSettings.general.language;
        
        // Update emergency status indicator
        this.updateEmergencyStatusIndicator();
        
        // Update language and restart auto-refresh
        this.updateLanguage();
        this.startAutoRefresh();
        
        this.closeSettings();
        
    } catch (error) {
        console.error('Error saving settings:', error);
        alert('Failed to save settings: ' + error.message);
    }
};

App.testEmail = async function() {
    try {
        const response = await fetch('/api/test-email', { method: 'POST' });
        const result = await response.json();
        
        // Backend returns {status: 'success/error', message: '...'} 
        if (result.status === 'success' || response.ok) {
            alert('Test e-post sendt! Sjekk innboksen din.');
        } else {
            alert('Kunne ikke sende test e-post: ' + (result.message || result.error || 'Ukjent feil'));
        }
    } catch (error) {
        console.error('Error testing email:', error);
        alert('Kunne ikke sende test e-post: ' + error.message);
    }
};

// ===== ABOUT MODAL =====
App.openAbout = function() {
    document.getElementById('aboutModal').classList.add('active');
};

App.closeAbout = function() {
    document.getElementById('aboutModal').classList.remove('active');
};

// ===== ALL LOGS MODAL =====
App.openAllLogs = async function() {
    const modal = document.getElementById('allLogsModal');
    const listContainer = document.getElementById('all-logs-list');
    
    // Show modal
    modal.classList.add('active');
    
    // Show loading
    listContainer.innerHTML = `
        <div class="loading-spinner">
            <div class="spinner"></div>
            <p data-i18n="loading_logs">Laster loggfiler...</p>
        </div>
    `;
    
    try {
        const response = await fetch('/api/logs/all');
        const data = await response.json();
        
        if (!data.disks || data.disks.length === 0) {
            listContainer.innerHTML = `
                <p class="no-data" data-i18n="no_logs_available">Ingen loggfiler funnet.</p>
            `;
            return;
        }
        
        // Render log list
        let html = '<div class="log-items">';
        for (const disk of data.disks) {
            const healthBadge = disk.last_health_score !== null && disk.last_health_score !== undefined
                ? `<span class="health-badge ${this.getHealthClass(disk.last_health_score)}">${disk.last_health_score}</span>`
                : '<span class="health-badge">N/A</span>';
            
            // Add GDC indicator if disk has GDC history
            const gdcIndicator = disk.has_gdc ? '💀' : '💾';
            const gdcClass = disk.has_gdc ? 'gdc-disk' : '';
            const gdcTitle = disk.has_gdc ? `GDC ${disk.gdc_state || 'UNKNOWN'}` : disk.model;
            
            html += `
                <div class="log-item ${gdcClass}">
                    <div class="log-item-header">
                        <h3 title="${this.escapeHtml(gdcTitle)}">${gdcIndicator} ${this.escapeHtml(disk.model)}</h3>
                        ${healthBadge}
                    </div>
                    <div class="log-item-details">
                        <p><strong>Serial:</strong> ${disk.serial}</p>
                        <p><strong>Sist sett:</strong> ${new Date(disk.last_seen).toLocaleString('no-NO')}</p>
                        <p><strong>Loggoppføringer:</strong> ${disk.total_entries.toLocaleString()}</p>
                    </div>
                    <div class="log-item-actions">
                        <button class="btn-secondary btn-small btn-view-log-from-list" data-model="${this.escapeHtml(disk.model)}" data-serial="${this.escapeHtml(disk.serial)}">
                            📄 Vis logg
                        </button>
                        <button class="btn-info btn-small btn-view-history-from-list" data-model="${this.escapeHtml(disk.model)}" data-serial="${this.escapeHtml(disk.serial)}">
                            📊 Vis historikk
                        </button>
                    </div>
                </div>
            `;
        }
        html += '</div>';
        
        listContainer.innerHTML = html;
        
        // Add event listeners to buttons
        listContainer.querySelectorAll('.btn-view-log-from-list').forEach(btn => {
            btn.addEventListener('click', () => {
                const model = btn.getAttribute('data-model');
                const serial = btn.getAttribute('data-serial');
                this.viewLogFromList(model, serial);
            });
        });
        
        listContainer.querySelectorAll('.btn-view-history-from-list').forEach(btn => {
            btn.addEventListener('click', () => {
                const model = btn.getAttribute('data-model');
                const serial = btn.getAttribute('data-serial');
                this.viewHistoryFromList(model, serial);
            });
        });
    } catch (error) {
        console.error('Error loading all logs:', error);
        listContainer.innerHTML = `
            <p class="error-text">Kunne ikke laste loggfiler: ${error.message}</p>
        `;
    }
};

App.closeAllLogs = function() {
    document.getElementById('allLogsModal').classList.remove('active');
};

App.viewLogFromList = function(model, serial) {
    // Close all logs modal and open log modal
    this.closeAllLogs();
    
    // Create a fake device object to pass to viewLog
    const fakeDevice = { model, serial, name: `${model}_${serial}` };
    this.viewLog(fakeDevice);
};

App.viewHistoryFromList = function(model, serial) {
    // Close all logs modal and open history modal
    this.closeAllLogs();
    
    // Create a fake device object to pass to viewHistory
    const fakeDevice = { model, serial, name: `${model}_${serial}` };
    this.viewHistory(fakeDevice);
};

// ===== PRINT REPORT =====
App.printReport = function() {
    // Prepare print view
    const printDate = new Date().toLocaleString('no-NO', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
    });
    
    // Add print timestamp to header
    const header = document.querySelector('header h1');
    const originalText = header.textContent;
    header.textContent = `${originalText} - ${this.t('report_generated')}: ${printDate}`;
    
    // Trigger print dialog
    window.print();
    
    // Restore header text after print
    setTimeout(() => {
        header.textContent = originalText;
    }, 100);
};

// ===== PRINT HISTORY (GRAPHS) =====
App.printHistory = function() {
    const historyTitle = document.getElementById('history-title');
    const titleText = historyTitle.querySelector('span')?.textContent || 'Disk History';
    
    // Detect active period
    const activePeriodBtn = historyTitle.querySelector('.btn-period.active');
    const periodText = activePeriodBtn ? activePeriodBtn.textContent : '';
    const fullTitle = periodText ? `${titleText} - ${periodText}` : titleText;
    
    const printDate = new Date().toLocaleString('no-NO', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
    });
    
    // Get only active chart containers (exclude chart-selection and inactive charts)
    const activeCharts = [];
    const chartContainers = document.querySelectorAll('#history-content .chart-container');
    chartContainers.forEach(container => {
        const canvas = container.querySelector('canvas');
        if (canvas && canvas.style.display !== 'none') {
            activeCharts.push(container.cloneNode(true));
        }
    });
    
    // Open new window for printing
    const printWindow = window.open('', '_blank', 'width=1200,height=800');
    
    printWindow.document.write(`
        <!DOCTYPE html>
        <html>
        <head>
            <title>${fullTitle} - Print</title>
            <style>
                * {
                    margin: 0;
                    padding: 0;
                    box-sizing: border-box;
                }
                body {
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                    padding: 20px;
                    background: white;
                }
                h1 {
                    font-size: 20px;
                    margin-bottom: 10px;
                    padding-bottom: 10px;
                    border-bottom: 2px solid #333;
                }
                .print-info {
                    font-size: 12px;
                    color: #666;
                    margin-bottom: 20px;
                }
                #history-content {
                    display: grid;
                    grid-template-columns: 1fr 1fr;
                    gap: 20px;
                }
                .chart-container {
                    page-break-inside: avoid;
                    height: 350px;
                    position: relative;
                }
                .chart-title {
                    font-size: 14px;
                    font-weight: bold;
                    margin-bottom: 8px;
                }
                canvas {
                    width: 100% !important;
                    height: calc(100% - 30px) !important;
                }
                @media print {
                    body { padding: 10px; }
                    #history-content {
                        grid-template-columns: 1fr 1fr;
                        gap: 15px;
                    }
                    .chart-container {
                        height: 320px;
                    }
                }
            </style>
            <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
        </head>
        <body>
            <h1>${fullTitle}</h1>
            <div class="print-info">Report generated: ${printDate}</div>
            <div id="history-content"></div>
            <script>
                // Will be populated after Charts are ready
            </script>
        </body>
        </html>
    `);
    
    printWindow.document.close();
    
    // Wait for Chart.js to load, then recreate charts
    setTimeout(() => {
        const container = printWindow.document.getElementById('history-content');
        
        // Add only active charts
        activeCharts.forEach(chartContainer => {
            container.appendChild(chartContainer);
        });
        
        // Get chart data from current window and recreate
        const chartTypes = ['health', 'temp', 'reallocated', 'pending', 'uncorrectable', 'mosmart188'];
        
        chartTypes.forEach(type => {
            if (this.charts[type]) {
                const ctx = printWindow.document.getElementById(`${type}-chart`);
                if (ctx) {
                    const chartData = {
                        type: this.charts[type].config.type,
                        data: this.charts[type].config.data,
                        options: this.charts[type].config.options
                    };
                    new printWindow.Chart(ctx, chartData);
                }
            }
        });
        
        // Auto-print after charts render
        setTimeout(() => {
            printWindow.print();
        }, 500);
    }, 500);
};

// ===== DISK LABEL PRINTER =====
App.printDiskLabel = function(deviceName) {
    // Fetch label data
    fetch(`/api/device/${deviceName}/label-data`)
        .then(response => response.json())
        .then(data => {
            if (data.status === 'error') {
                alert('Kunne ikke hente data for disk: ' + data.message);
                return;
            }
            
            // Build print HTML
            const printWindow = window.open('', '', 'width=400,height=600');
            
            // Format data
            const healthStars = '★'.repeat(Math.ceil(data.health_score / 20));
            const powerOnTime = this.formatPowerOnTime(data.power_on_hours);
            const writtenData = data.total_bytes_written ? 
                this.formatBytes(data.total_bytes_written) : 'N/A';
            
            // Smart max temp: prioritize SMART 194 worst, fallback to MoSMART observation
            let maxTempStr = '';
            if (data.smart_max_temperature) {
                maxTempStr = ` (max: ${data.smart_max_temperature}°C)`;
            } else if (data.mosmart194_max_temperature) {
                maxTempStr = ` (max: MoSMART: ${data.mosmart194_max_temperature}°C)`;
            }
            
            // Check for current errors (not past_failures)
            const hasCurrentErrors = data.reallocated_sectors > 0 || 
                            data.pending_sectors > 0 || 
                            data.uncorrectable_errors > 0 ||
                            data.mosmart188 > 0;
            
            const hasPastFailures = data.past_failures && data.past_failures.length > 0;
            
            let html = `
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title></title>
    <style>
        @page {
            size: A7 landscape;
            margin: 10mm 3mm 3mm 10mm;
        }
        
        @media print {
            body { margin: 10mm; }
            @page { margin: 0; }
        }
        
        body {
            font-family: 'Arial', sans-serif;
            font-size: 9pt;
            line-height: 1.3;
            padding: 2mm;
            width: 99mm;
            height: 68mm;
        }
        
        .header {
            display: flex;
            align-items: center;
            gap: 4mm;
            margin-bottom: 2mm;
            border-bottom: 1px solid #000;
            padding-bottom: 1mm;
        }
        
        .logo {
            width: 8mm;
            height: 8mm;
        }
        
        .title {
            font-weight: bold;
            font-size: 11pt;
        }
        
        .status {
            font-size: 10pt;
            font-weight: bold;
            margin: 1mm 0;
        }
        
        .info-row {
            margin: 0.5mm 0;
            font-size: 8pt;
        }
        
        .section {
            margin-top: 2mm;
            padding-top: 1mm;
            border-top: 1px dashed #666;
        }
        
        .error {
            font-weight: bold;
        }
        
        .footer {
            margin-top: 2mm;
            font-size: 7pt;
            color: #666;
        }
    </style>
</head>
<body>
    <div class="header">
        <img src="/static/modig-logo-monokrom.png" class="logo" alt="Logo">
        <div class="title">MoSMART Rapport</div>
    </div>
    
    <div class="status">
        Status: ${healthStars} ${data.health_rating} (${data.health_score})
    </div>
    
    <div class="info-row">Temp: ${data.temperature || 'N/A'}°C${maxTempStr}</div>
    <div class="info-row">Driftstid: ${powerOnTime} (${data.power_on_hours.toLocaleString()} t)</div>
    
    ${data.is_ssd ? `
    <div class="section">
        <div class="info-row">Skrevet: ${writtenData}</div>
    </div>
    ` : `
    <div class="section">
        <div class="info-row">Power Cycles: ${data.power_cycles.toLocaleString()}</div>
    </div>
    `}
    
    ${hasCurrentErrors ? `
    <div class="section">
        ${data.reallocated_sectors > 0 ? `<div class="info-row error">Reallocated: ${data.reallocated_sectors}</div>` : ''}
        ${data.pending_sectors > 0 ? `<div class="info-row error">Pending: ${data.pending_sectors}</div>` : ''}
        ${data.uncorrectable_errors > 0 ? `<div class="info-row error">Uncorrectable: ${data.uncorrectable_errors}</div>` : ''}
        ${data.mosmart188 > 0 ? `<div class="info-row error">mosmart188: ${data.mosmart188} (disk restarts)</div>` : ''}
    </div>
    ` : `
    <div class="section">
        <div class="info-row">✓ Ingen mekaniske feil pr. ${data.date}</div>
    </div>
    `}
    
    ${hasPastFailures ? `
    <div class="section">
        <div class="info-row error">⚠ Tidligere feil: ${data.past_failures.map(f => this.t(f.display_name) || f.name).join(', ')}</div>
    </div>
    ` : ``}
    
    <div class="footer">
        <div>${data.model}</div>
        <div>S/N: ${data.serial}</div>
    </div>
</body>
</html>
            `;
            
            printWindow.document.write(html);
            printWindow.document.close();
            
            // Trigger print dialog after content loads
            printWindow.onload = function() {
                setTimeout(() => {
                    printWindow.print();
                    printWindow.close();
                }, 250);
            };
        })
        .catch(error => {
            alert('Feil ved henting av label-data: ' + error.message);
            console.error('Label print error:', error);
        });
};

App.formatBytes = function(bytes) {
    if (!bytes || bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB', 'PB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
};

App.formatPowerOnTime = function(hours) {
    if (!hours) return '0 timer';
    
    const months = Math.floor(hours / 730);
    const remainingHours = hours % 730;
    const days = Math.floor(remainingHours / 24);
    const hrs = remainingHours % 24;
    
    if (months > 0) {
        return `${months} md, ${days} d`;
    } else if (days > 0) {
        return `${days} d, ${hrs} t`;
    } else {
        return `${hrs} t`;
    }
};

// ===== EMERGENCY UNMOUNT =====
App.updateEmergencyUnmountStatus = function(mode) {
    const indicator = document.getElementById('emergency-mode-indicator');
    if (!indicator) return;
    
    if (mode === 'ACTIVE') {
        indicator.textContent = 'ACTIVE (unmount enabled)';
        indicator.className = 'status-badge active';
    } else {
        indicator.textContent = 'PASSIVE (trygt - kun logging)';
        indicator.className = 'status-badge passive';
    }
    
    // Also update header indicator
    this.updateEmergencyStatusIndicator();
};

App.updateEmergencyStatusIndicator = function() {
    const indicator = document.getElementById('emergency-status-indicator');
    if (!indicator) return;
    
    const mode = this.state.settings?.emergency_unmount?.mode || 'PASSIVE';
    const statusText = indicator.querySelector('.status-text');
    
    if (mode === 'ACTIVE') {
        indicator.className = 'emergency-status active';
        indicator.title = 'Nødstopp AKTIVERT - Klikk for å endre';
        if (statusText) {
            statusText.setAttribute('data-i18n', 'emergency_active');
            statusText.textContent = 'Nødstopp: PÅ';
        }
    } else {
        indicator.className = 'emergency-status passive';
        indicator.title = 'Nødstopp AV - Klikk for å endre';
        if (statusText) {
            statusText.setAttribute('data-i18n', 'emergency_passive');
            statusText.textContent = 'Nødstopp: AV';
        }
    }
};

App.testEmergencyUnmount = function() {
    // Test emergency unmount system - validation and simulation only
    if (!confirm('Dette vil kjøre en simulering av emergency unmount-systemet.\n\nINGEN disker vil bli unmountet.\n\nVil du fortsette?')) {
        return;
    }
    
    fetch('/api/emergency-unmount/test')
        .then(response => response.json())
        .then(data => {
            if (data.status === 'error') {
                alert('Feil ved test: ' + data.message);
                return;
            }
            
            const v = data.validation;
            const s = data.simulation || [];
            
            // Build test report
            let report = '🧪 EMERGENCY UNMOUNT TEST REPORT\n\n';
            report += '═══════════════════════════════════════\n';
            report += 'SYSTEM VALIDATION\n';
            report += '═══════════════════════════════════════\n\n';
            
            report += `✓ Emergency module: ${v.emergency_module ? '✅ Available' : '❌ NOT FOUND'}\n`;
            report += `✓ umount command: ${v.umount_command ? '✅ Available' : '❌ NOT FOUND'}\n`;
            report += `✓ Current mode: ${v.current_mode === 'ACTIVE' ? '🔴 ACTIVE' : '🟢 PASSIVE'}\n`;
            report += `✓ Sudo access: ${v.sudo_access ? '✅ Yes (root)' : '❌ No'}\n\n`;
            
            if (s.length > 0) {
                report += '═══════════════════════════════════════\n';
                report += 'DISK SIMULATION (IF EMERGENCY)\n';
                report += '═══════════════════════════════════════\n\n';
                
                s.forEach(disk => {
                    report += `📀 ${disk.device} - ${disk.model}\n`;
                    report += `   Mountpoint: ${disk.mountpoint || 'Not mounted'}\n`;
                    
                    if (disk.would_unmount) {
                        report += `   ✅ WOULD UNMOUNT: ${disk.reason}\n`;
                    } else {
                        report += `   🚫 BLOCKED: ${disk.reason}\n`;
                    }
                    
                    if (disk.is_critical) {
                        report += `   ⚠️  CRITICAL PATH - Always protected\n`;
                    }
                    
                    report += '\n';
                });
            }
            
            report += '═══════════════════════════════════════\n';
            report += 'SUMMARY\n';
            report += '═══════════════════════════════════════\n\n';
            
            const canUnmount = s.filter(d => d.would_unmount).length;
            const blocked = s.filter(d => !d.would_unmount && d.mountpoint).length;
            
            report += `Disks that would be unmounted: ${canUnmount}\n`;
            report += `Disks protected (critical/not mounted): ${blocked}\n\n`;
            
            if (!v.emergency_module) {
                report += '⚠️  WARNING: Emergency module not available!\n';
            }
            if (!v.sudo_access) {
                report += '⚠️  WARNING: Not running as root - unmount would fail!\n';
            }
            if (v.current_mode === 'PASSIVE') {
                report += 'ℹ️  INFO: Currently in PASSIVE mode - no actions taken\n';
            }
            
            // Show in alert (scrollable)
            alert(report);
        })
        .catch(error => {
            alert('Feil ved test: ' + error.message);
            console.error('Emergency unmount test error:', error);
        });
};

App.openEmergencyUnmountDocs = function() {
    // Deprecated: use openDocumentation instead
    this.openDocumentation();
};

App.openDocumentation = function() {
    // Open documentation based on current language with fallback to English
    const lang = this.config.language || 'en';
    let docUrl;
    
    if (lang === 'no') {
        docUrl = '/dokumentasjon-no.md';
    } else if (lang === 'en') {
        docUrl = '/documentation-en.md';
    } else {
        // Fallback to English for unknown languages
        docUrl = '/documentation-en.md';
    }
    
    window.open(docUrl, '_blank');
};

// ===== LANGUAGE =====
App.toggleLanguage = function() {
    this.config.language = this.config.language === 'no' ? 'en' : 'no';
    this.updateLanguage();
};

App.updateLanguage = function() {
    const lang = this.config.language;
    
    // Update all translatable elements
    document.querySelectorAll('[data-i18n]').forEach(elem => {
        const key = elem.getAttribute('data-i18n');
        const translation = this.translations[lang][key];
        if (translation) {
            elem.textContent = translation;
        }
    });
    
    // Update language button
    const langBtn = document.getElementById('lang-btn');
    if (langBtn) {
        langBtn.textContent = lang === 'no' ? '🇬🇧 EN' : '🇳🇴 NO';
    }
    
    // Re-render to apply translations
    this.renderDevices();
};

// Close modals on outside click
window.onclick = function(event) {
    if (event.target.classList.contains('modal')) {
        event.target.classList.remove('active');
    }
};
