const form = document.getElementById('resolveForm');
const submitBtn = document.getElementById('submitBtn');
const loading = document.getElementById('loading');
const error = document.getElementById('error');
const results = document.getElementById('results');
const dnsServerSelect = document.getElementById('dnsServer');
const customDnsServerGroup = document.getElementById('customDnsServerGroup');
const customDnsServerInput = document.getElementById('customDnsServer');
const formatSelect = document.getElementById('format');
const gatewayGroup = document.getElementById('gatewayGroup');
const wireguardSection = document.getElementById('wireguardSection');
const keeneticSection = document.getElementById('keeneticSection');
const gatewayInput = document.getElementById('gateway');

const state = {
    result: null,
};

function clearFieldErrors() {
    document.querySelectorAll('.field-error').forEach((node) => {
        node.textContent = '';
        node.classList.remove('visible');
    });
}

function setFieldError(id, message) {
    const node = document.getElementById(id);
    if (!node) {
        return;
    }
    node.textContent = message;
    node.classList.add('visible');
}

function isValidIpv4(value) {
    const parts = value.split('.');
    if (parts.length !== 4) {
        return false;
    }

    return parts.every((part) => {
        if (!/^\d+$/.test(part)) {
            return false;
        }

        const number = Number(part);
        return number >= 0 && number <= 255;
    });
}

function updateDnsServerUi() {
    if (dnsServerSelect.value === 'custom') {
        customDnsServerGroup.classList.remove('hidden');
    } else {
        customDnsServerGroup.classList.add('hidden');
    }
}

function updateGatewayUi() {
    if (formatSelect.value === 'keenetic') {
        gatewayGroup.classList.remove('hidden');
    } else {
        gatewayGroup.classList.add('hidden');
    }
}

function validateForm() {
    clearFieldErrors();

    const dns = document.getElementById('dns').value.trim();
    const timeout = Number(document.getElementById('timeout').value);
    const maxDepth = Number(document.getElementById('maxDepth').value);
    const waitAfterLoad = Number(document.getElementById('waitAfterLoad').value);
    const dnsServer = dnsServerSelect.value;
    const customDnsServer = customDnsServerInput.value.trim();
    const gateway = gatewayInput.value.trim();

    let hasErrors = false;

    if (!dns) {
        setFieldError('dnsError', 'Enter a domain name or URL.');
        hasErrors = true;
    }

    if (!Number.isInteger(timeout) || timeout < 1 || timeout > 300) {
        setFieldError('timeoutError', 'Timeout must be an integer from 1 to 300.');
        hasErrors = true;
    }

    if (!Number.isInteger(maxDepth) || maxDepth < 0 || maxDepth > 10) {
        setFieldError('maxDepthError', 'Depth must be an integer from 0 to 10.');
        hasErrors = true;
    }

    if (!Number.isInteger(waitAfterLoad) || waitAfterLoad < 0) {
        setFieldError('waitAfterLoadError', 'Wait time must be an integer of 0 or greater.');
        hasErrors = true;
    }

    if (dnsServer === 'custom') {
        if (!customDnsServer) {
            setFieldError('customDnsServerError', 'Enter a custom DNS server address.');
            hasErrors = true;
        } else if (!isValidIpv4(customDnsServer)) {
            setFieldError('customDnsServerError', 'Custom DNS server must be a valid IPv4 address.');
            hasErrors = true;
        }
    }

    if (formatSelect.value === 'keenetic' && gateway && !isValidIpv4(gateway)) {
        setFieldError('gatewayError', 'Gateway must be a valid IPv4 address.');
        hasErrors = true;
    }

    return !hasErrors;
}

function renderItems(containerId, items, emptyMessage = 'No data to display.') {
    const container = document.getElementById(containerId);
    container.replaceChildren();

    if (!items.length) {
        const emptyNode = document.createElement('div');
        emptyNode.className = 'result-empty';
        emptyNode.textContent = emptyMessage;
        container.appendChild(emptyNode);
        return;
    }

    items.forEach((item) => {
        const itemNode = document.createElement('div');
        itemNode.className = 'result-item';
        itemNode.textContent = item;
        container.appendChild(itemNode);
    });
}

function buildWireguardLines(ips) {
    if (!ips.length) {
        return [];
    }

    return [`AllowedIPs = ${ips.map((ip) => `${ip}/32`).join(', ')}`];
}

function buildKeeneticLines(ips, gateway) {
    if (!ips.length) {
        return [];
    }

    return ips.map((ip) => `route add ${ip} mask 255.255.255.255 ${gateway}`);
}

function updateDisplay() {
    if (!state.result) {
        return;
    }

    const format = formatSelect.value;
    const result = state.result;

    wireguardSection.classList.add('hidden');
    keeneticSection.classList.add('hidden');

    if (format === 'wireguard') {
        renderItems('resultWireguard', buildWireguardLines(result.ips), 'No IPs found. WireGuard configuration was not generated.');
        wireguardSection.classList.remove('hidden');
    } else if (format === 'keenetic') {
        const gateway = gatewayInput.value.trim() || '10.0.0.18';
        renderItems('resultKeenetic', buildKeeneticLines(result.ips, gateway), 'No IPs found. Keenetic commands were not generated.');
        keeneticSection.classList.remove('hidden');
    }
}

formatSelect.addEventListener('change', () => {
    updateGatewayUi();

    if (state.result) {
        updateDisplay();
    }
});

dnsServerSelect.addEventListener('change', () => {
    updateDnsServerUi();
});

gatewayInput.addEventListener('input', () => {
    if (state.result && formatSelect.value === 'keenetic') {
        updateDisplay();
    }
});

function downloadResult() {
    if (!state.result) {
        return;
    }

    const format = formatSelect.value;
    const result = state.result;
    let content = '';
    let filename = '';
    const mimeType = 'text/plain';

    if (format === 'ips') {
        content = result.ips.join('\n');
        filename = `${result.hostname}_ips.txt`;
    } else if (format === 'wireguard') {
        content = buildWireguardLines(result.ips).join('\n');
        filename = `${result.hostname}_wireguard.conf`;
    } else if (format === 'keenetic') {
        const gateway = gatewayInput.value.trim() || '10.0.0.18';
        content = buildKeeneticLines(result.ips, gateway).join('\n');
        filename = `${result.hostname}_keenetic.txt`;
    }

    const blob = new Blob([content], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
}

document.getElementById('downloadBtn').addEventListener('click', downloadResult);

updateDnsServerUi();
updateGatewayUi();

form.addEventListener('submit', async (e) => {
    e.preventDefault();

    if (!validateForm()) {
        results.classList.remove('visible');
        return;
    }

    const formData = new FormData(form);
    const data = {
        dns: String(formData.get('dns') || '').trim(),
        timeout: parseInt(formData.get('timeout'), 10),
        max_depth: parseInt(formData.get('maxDepth'), 10),
        wait_after_load: parseInt(formData.get('waitAfterLoad'), 10),
        dns_server: String(formData.get('dnsServer') || 'both'),
        custom_dns_server: String(formData.get('customDnsServer') || '').trim(),
        format: formData.get('format'),
        gateway: String(formData.get('gateway') || '').trim(),
    };

    clearFieldErrors();
    loading.classList.add('visible');
    error.classList.remove('visible');
    results.classList.remove('visible');
    submitBtn.disabled = true;
    state.result = null;

    try {
        const response = await fetch('/resolve', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data),
        });

        if (!response.ok) {
            const rawError = await response.text();
            let message = `HTTP error: ${response.status}`;

            try {
                const errorData = JSON.parse(rawError);
                if (errorData.detail) {
                    message = errorData.detail;
                }
            } catch {
                if (rawError.trim()) {
                    message = rawError.trim();
                }
            }

            throw new Error(message);
        }

        const result = await response.json();
        const sortedIps = [...result.ips].sort();

        document.getElementById('resultHostname').textContent = result.hostname;
        document.getElementById('resultCount').textContent = result.count;
        renderItems('resultIps', sortedIps, 'No IP addresses were found for the specified input.');

        state.result = {
            ...result,
            ips: sortedIps,
        };
        updateDisplay();

        results.classList.add('visible');
    } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to process the request.';
        error.textContent = `Error: ${message}`;
        error.classList.add('visible');
    } finally {
        loading.classList.remove('visible');
        submitBtn.disabled = false;
    }
});