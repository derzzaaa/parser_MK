// ===== MARKETPLACE TOGGLE =====
let currentMarketplace = 'avito';
const sessionResults = {
    'avito': null,
    'yandex': null,
    'ozon': null,
    'wb': null
};

// Current rendered results (for filtering)
let currentRenderedResults = [];

function setMarketplace(mp) {
    currentMarketplace = mp;
    document.getElementById('btnAvito').classList.toggle('active', mp === 'avito');
    document.getElementById('btnYandex').classList.toggle('active', mp === 'yandex');
    document.getElementById('btnOzon').classList.toggle('active', mp === 'ozon');
    document.getElementById('btnWb').classList.toggle('active', mp === 'wb');

    // Город только для Авито
    const cityFilter = document.getElementById('cityFilterCol');
    if (cityFilter) {
        cityFilter.style.display = mp === 'avito' ? 'block' : 'none';
    }

    // Обновляем ссылку
    const link = document.getElementById('marketLink');
    if (link) {
        if (mp === 'avito') link.textContent = '🔗 Открыть на Авито';
        else if (mp === 'yandex') link.textContent = '🔗 Открыть на Яндекс Маркете';
        else if (mp === 'ozon') link.textContent = '🔗 Открыть на Ozon';
        else link.textContent = '🔗 Открыть на Wildberries';
    }

    // Восстанавливаем или очищаем результаты
    const cached = sessionResults[mp];
    if (cached) {
        // Убираем ошибку и показываем кэшированные данные
        hideError();
        renderResults(cached.results, cached.query, cached.city);
    } else {
        // Пока ничего не искали на этом маркетплейсе
        hide('resultsSection');
        document.getElementById('resultsContainer').innerHTML = '';
        hideError();
        clearDescriptionFilter();
    }
}

// ===== SEARCH FORM =====
document.getElementById('searchForm').addEventListener('submit', async (e) => {
    e.preventDefault();

    const query = document.getElementById('searchQuery').value.trim();
    const city = document.getElementById('city').value;
    const maxResults = document.getElementById('maxResults').value;

    if (!query) { showError('Введите поисковый запрос'); return; }

    // Валидация цены
    const pMin = document.getElementById('priceMin').value;
    const pMax = document.getElementById('priceMax').value;
    if (pMin && pMax && parseInt(pMin) >= parseInt(pMax)) {
        showError('Цена "От" должна быть меньше цены "До"');
        document.getElementById('priceMin').style.borderColor = '#e74c3c';
        document.getElementById('priceMax').style.borderColor = '#e74c3c';
        return;
    }
    // Сбрасываем подсветку если всё ок
    document.getElementById('priceMin').style.borderColor = '#111';
    document.getElementById('priceMax').style.borderColor = '#111';

    setLoading(true);
    hideError();
    hide('resultsSection');
    clearDescriptionFilter();

    try {
        const res = await fetch('/search', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                query,
                max_results: parseInt(maxResults),
                city,
                marketplace: currentMarketplace,
                price_min: document.getElementById('priceMin').value || null,
                price_max: document.getElementById('priceMax').value || null,
            })
        });

        const data = await res.json();

        if (data.success) {
            sessionResults[currentMarketplace] = {
                results: data.results,
                query: query,
                city: city
            };
            renderResults(data.results, query, city);

            if (data.total_records !== undefined)
                document.getElementById('recordCount').textContent = data.total_records;

            if (data.saved_to_excel) {
                show('excelSaved');
                setTimeout(() => hide('excelSaved'), 4000);
            }
        } else {
            showError(data.error || 'Ошибка при поиске');
        }

    } catch (err) {
        showError('Не удалось подключиться к серверу');
        console.error(err);
    } finally {
        setLoading(false);
    }
});

// ===== RENDER RESULTS =====
function renderResults(results, query, city) {
    if (!results || results.length === 0) {
        showError(`По запросу "${query}" ничего не найдено`);
        return;
    }

    // Store for filtering
    currentRenderedResults = results;

    // Count
    document.getElementById('resultsCount').textContent = `${results.length} шт.`;

    // Marketplace link
    const citySlug = { kazan: 'kazan', moskva: 'moskva', spb: 'sankt-peterburg', rossiya: 'rossiya' };
    const slug = citySlug[city] || 'rossiya';
    const link = document.getElementById('marketLink');
    if (currentMarketplace === 'avito') {
        link.href = `https://www.avito.ru/${slug}?q=${encodeURIComponent(query)}&s=104`;
        link.textContent = '🔗 Открыть на Авито';
    } else if (currentMarketplace === 'yandex') {
        link.href = `https://market.yandex.ru/search?text=${encodeURIComponent(query)}`;
        link.textContent = '🔗 Открыть на Яндекс Маркете';
    } else if (currentMarketplace === 'ozon') {
        link.href = `https://www.ozon.ru/search/?text=${encodeURIComponent(query)}`;
        link.textContent = '🔗 Открыть на Ozon';
    } else {
        link.href = `https://www.wildberries.ru/catalog/0/search.aspx?search=${encodeURIComponent(query)}`;
        link.textContent = '🔗 Открыть на Wildberries';
    }
    link.style.display = 'flex';

    // Cards
    const container = document.getElementById('resultsContainer');
    container.innerHTML = '';

    results.forEach((p, i) => {
        const card = document.createElement('div');
        card.className = 'product-card';
        card.style.animationDelay = `${i * 0.05}s`;
        // Store description data on the card element for filtering
        const descText = buildSearchableText(p);
        card.setAttribute('data-description', descText.toLowerCase());

        const title = el('div', 'product-title', p.title);
        const price = el('div', 'product-price', p.price || 'Цена не указана');

        // Бейдж маркетплейса
        const mpNames = { avito: 'Авито', yandex: 'Яндекс Маркет', ozon: 'Ozon', wb: 'Wildberries' };
        const badge = el('span', 'product-badge mp-' + currentMarketplace, mpNames[currentMarketplace] || '');

        const link = document.createElement('a');
        link.className = 'product-link';
        link.href = p.url || '#';
        link.target = '_blank';
        link.textContent = 'Открыть товар';

        card.appendChild(badge);
        card.appendChild(title);

        // Description (всегда показываем, если есть)
        if (p.description && p.description.trim()) {
            const desc = el('div', 'product-description', p.description);
            card.appendChild(desc);
        }

        card.appendChild(price);
        if (p.rating) {
            const rating = el('div', 'product-rating', `⭐ ${p.rating}`);
            card.appendChild(rating);
        }
        card.appendChild(link);

        container.appendChild(card);
    });

    show('resultsSection');
    // Reset filter when new results are rendered
    clearDescriptionFilter();
    setTimeout(() => document.getElementById('resultsSection').scrollIntoView({ behavior: 'smooth', block: 'start' }), 120);
}

// ===== DESCRIPTION FILTER =====

/**
 * Build a searchable text string from all product fields.
 * Since different marketplaces have different structures,
 * we combine everything available for maximum search coverage.
 */
function buildSearchableText(product) {
    const parts = [
        product.title || '',
        product.description || '',
        product.price || '',
        product.rating || '',
        product.location || '',
    ];
    return parts.join(' ');
}

/**
 * Filter product cards by keywords typed in the description filter input.
 * All keywords must be present (AND logic) in the product's combined text.
 */
function applyDescriptionFilter() {
    const filterInput = document.getElementById('descriptionFilter');
    const filterValue = filterInput.value.trim().toLowerCase();
    const clearBtn = document.getElementById('clearFilterBtn');
    const filterInfo = document.getElementById('filterInfo');
    const cards = document.querySelectorAll('#resultsContainer .product-card');

    // Show/hide clear button
    clearBtn.style.display = filterValue ? 'flex' : 'none';

    if (!filterValue) {
        // No filter — show all cards
        cards.forEach(card => card.classList.remove('filtered-out'));
        filterInfo.style.display = 'none';
        // Restore original count
        if (currentRenderedResults.length > 0) {
            document.getElementById('resultsCount').textContent = `${currentRenderedResults.length} шт.`;
        }
        return;
    }

    // Split keywords
    const keywords = filterValue.split(/\s+/).filter(k => k.length > 0);

    let visibleCount = 0;
    let totalCount = cards.length;

    cards.forEach(card => {
        const descData = card.getAttribute('data-description') || '';

        // Check that ALL keywords are present
        const matches = keywords.every(kw => descData.includes(kw));

        if (matches) {
            card.classList.remove('filtered-out');
            visibleCount++;
        } else {
            card.classList.add('filtered-out');
        }
    });

    // Update counter and info
    document.getElementById('resultsCount').textContent = `${visibleCount} из ${totalCount}`;

    if (visibleCount === 0) {
        filterInfo.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#e74c3c" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg> <span style="color:#e74c3c">Ничего не найдено по ключевым словам «${escapeHtml(filterValue)}»</span>`;
    } else {
        filterInfo.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#667eea" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg> Показано <span class="filter-count">${visibleCount}</span> из ${totalCount} товаров по фильтру «${escapeHtml(filterValue)}»`;
    }
    filterInfo.style.display = 'flex';
}

function clearDescriptionFilter() {
    const filterInput = document.getElementById('descriptionFilter');
    if (filterInput) {
        filterInput.value = '';
    }
    const clearBtn = document.getElementById('clearFilterBtn');
    if (clearBtn) {
        clearBtn.style.display = 'none';
    }
    const filterInfo = document.getElementById('filterInfo');
    if (filterInfo) {
        filterInfo.style.display = 'none';
    }
    // Show all cards
    const cards = document.querySelectorAll('#resultsContainer .product-card');
    cards.forEach(card => card.classList.remove('filtered-out'));
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Event listeners for description filter
document.addEventListener('DOMContentLoaded', () => {
    const filterInput = document.getElementById('descriptionFilter');
    const clearBtn = document.getElementById('clearFilterBtn');

    if (filterInput) {
        // Filter on typing (with debounce)
        let debounceTimer;
        filterInput.addEventListener('input', () => {
            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(applyDescriptionFilter, 200);
        });

        // Also filter on Enter
        filterInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                clearTimeout(debounceTimer);
                applyDescriptionFilter();
            }
        });
    }

    if (clearBtn) {
        clearBtn.addEventListener('click', () => {
            clearDescriptionFilter();
            // Restore original count
            if (currentRenderedResults.length > 0) {
                document.getElementById('resultsCount').textContent = `${currentRenderedResults.length} шт.`;
            }
        });
    }
});

// ===== HELPERS =====
function el(tag, cls, text) {
    const e = document.createElement(tag);
    e.className = cls;
    e.textContent = text;
    return e;
}

function setLoading(on) {
    const indicator = document.getElementById('loadingIndicator');
    const btn = document.getElementById('searchBtn');
    const btnText = btn.querySelector('.btn-text');
    const loader = btn.querySelector('.loader-btn');

    indicator.style.display = on ? 'flex' : 'none';
    btn.disabled = on;
    btnText.style.display = on ? 'none' : 'inline';
    loader.style.display = on ? 'inline-block' : 'none';
}

function showError(msg) {
    const el = document.getElementById('errorMessage');
    el.textContent = msg;
    el.style.display = 'block';
    setTimeout(() => el.style.display = 'none', 5000);
}

function hideError() { document.getElementById('errorMessage').style.display = 'none'; }
function show(id) { document.getElementById(id).style.display = 'block'; }
function hide(id) { document.getElementById(id).style.display = 'none'; }

// Autofocus
window.addEventListener('load', () => document.getElementById('searchQuery').focus());
