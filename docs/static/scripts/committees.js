document.addEventListener("DOMContentLoaded", () => {
    let rawData = [];
    let initialLoad = true;

    const yearFilter = document.getElementById("year-filter");
    const seasonFilter = document.getElementById("season-filter");
    const searchInput = document.getElementById("show-search");
    const form = document.getElementById("filter-form");
    const container = document.querySelector(".committee-container");
    const emptyState = document.querySelector(".empty-state");
    const updateTime = document.getElementById("committee-update-time");
    const loadingIndicator = document.getElementById("loading-indicator");

    // Get the current year and season from the data attributes
    const currentYear = document.getElementById("committee-container").dataset.currentYear;
    const currentSeason = document.getElementById("committee-container").dataset.currentSeason;
    console.log("Current Year:", currentYear, "Current Season:", currentSeason);

    console.log("Initial selected year:", yearFilter.value);
    console.log("Initial selected season:", seasonFilter.value);


    // Show loading indicator
    function showLoading() {
        if (loadingIndicator) {
            loadingIndicator.classList.remove("hidden");
        }
    }

    // Hide loading indicator
    function hideLoading() {
        if (loadingIndicator) {
            loadingIndicator.classList.add("hidden");
        }
    }

    // Fetch JSON and initialize
    showLoading();
    fetch("static/data/committees.json")
        .then((res) => res.json())
        .then((data) => {
            rawData = data;
            populateYearFilter(data);

            // Set default filter values to current year and season
            if (currentYear) {
                yearFilter.value = currentYear;
            }
            if (currentSeason) {
                seasonFilter.value = currentSeason;
            }

            applyFilters();
            updateTime.textContent = new Date().toLocaleString();
            hideLoading();
        })
        .catch(error => {
            console.error("Error fetching committee data:", error);
            emptyState.classList.remove("hidden");
            emptyState.querySelector("p").textContent = "Error loading committee data";
            emptyState.querySelector("span").textContent = "Please try again later";
            hideLoading();
        });

    form.addEventListener("submit", (e) => {
        e.preventDefault();
        applyFilters();
    });

    // Add change event listeners to immediately apply filters when dropdowns change
    yearFilter.addEventListener("change", applyFilters);
    seasonFilter.addEventListener("change", applyFilters);
    searchInput.addEventListener("input", applyFilters);

    function populateYearFilter(data) {
        const years = [...new Set(data.map((show) => show.year))].sort((a, b) => b - a);
        years.forEach((year) => {
            const opt = document.createElement("option");
            opt.value = year;
            opt.textContent = year;
            yearFilter.appendChild(opt);
        });
    }

    function applyFilters() {
        showLoading();
        const season = seasonFilter.value;
        const year = yearFilter.value;
        const searchTerm = searchInput.value.toLowerCase();

        // make sure we have a year filter applied to avoid loading everything
        if (initialLoad && !searchTerm && year === "all") {
            yearFilter.value = currentYear || new Date().getFullYear().toString();
            initialLoad = false;
        }

        let filtered = rawData;

        // Apply filters
        if (season !== "all") {
            filtered = filtered.filter((show) => show.season === season);
        }

        if (year !== "all") {
            filtered = filtered.filter((show) => String(show.year) === year);
        }

        if (searchTerm) {
            filtered = filtered.filter((show) => {
                const title = (show.title_english || show.title || "").toLowerCase();
                const producers = (show.committee || []).map((p) => (p.name || "").toLowerCase());
                return title.includes(searchTerm) || producers.some((p) => p.includes(searchTerm));
            });
        }

        renderCommittees(filtered);
        hideLoading();
    }

    function renderCommittees(shows) {
        container.innerHTML = "";
        if (shows.length === 0) {
            emptyState.classList.remove("hidden");
            return;
        }
        emptyState.classList.add("hidden");

        shows.forEach((show) => {
            const image = show.images?.medium || "";
            const title = show.title_english || show.title || "Untitled";
            const score = show.score ? `<span class="score-badge"><i class="fa-solid fa-star"></i> ${show.score}</span>` : "";
            const url = show.url ? `<a href="${show.url}" class="mal-badge" target="_blank">MAL</a>` : "";

            const streamLinkHtml = show.streams && show.streams.url ?
                `<a href="${show.streams.url}" class="action-link stream-link" target="_blank">
                    ${show.streams.logo ?
                    `<img src="${show.streams.logo}" alt="${show.streams.service || 'Stream'}" class="stream-logo">` :
                    'Watch'
                }
                </a>` : '';

            const producers = (show.committee || [])
                .map((p) => {
                    const image = p.image ? `<img src="${p.image}" alt="${p.name}" class="producer-img">` : `<div class="producer-img placeholder-img"><i class="fa-solid fa-building"></i></div>`;
                    const flag = p.flag ? `<img src="${p.flag}" alt="${p.country}" class="country-flag" title="${p.country}">` : '';
                    let producerCardClass = "producer-card";
                    if (p.category && p.category.toLowerCase() === "animation studio") {
                        producerCardClass += " animation-studio";
                    }
                    return `
                    <div class="${producerCardClass}">
                        <div class="producer-header">${image}<h5 class="producer-name">${p.name} </h5>${flag}</div>
                        <div class="producer-meta">
                        ${p.established ? `<span class="established">Est. ${p.established.slice(0, 10)}</span>` : ""}
                        ${p.favorites ? `<span class="favorites"><i class="fa-solid fa-heart"></i> ${p.favorites}</span>` : ""}
                        </div>
                    </div>`;
                })
                .join("");
            
            let producerCardClass = "producer-card";
            if (show.category && show.category.toLowerCase() === "animation studio") {
                producerCardClass += " animation-studio";
            }

            const card = `
      <div class="committee-card" data-year="${show.year}" data-season="${show.season}">
        <div class="committee-header">
          <div class="anime-info">
            ${image ? `<img src="${image}" alt="${title}" class="anime-img">` : `<div class="anime-img placeholder-img"></div>`}
            <div class="anime-details">
              <h3 class="anime-title">${title}</h3>
              <div class="anime-meta">
                <span class="season-badge ${show.season}">${show.season} ${show.year}</span>
                ${score}
                ${url}
                ${streamLinkHtml}
              </div>
            </div>
          </div>
        </div>
        <div class="committee-members">
          <h4>Production Committee</h4>
          <div class="producer-grid">${producers}</div>
        </div>
      </div>`;

            container.insertAdjacentHTML("beforeend", card);
        });
    }
});