// Weekly Rankings historical data handler
document.addEventListener('DOMContentLoaded', function () {
    // Get references to selector elements
    const yearSelect = document.getElementById('year-select');
    const seasonSelect = document.getElementById('season-select');
    const weekSelect = document.getElementById('week-select');
    const loadButton = document.getElementById('load-week-btn');
    const weeklyTable = document.getElementById('weekly-ranking-table');

    // Add event listener to the load button
    if (loadButton) {
        loadButton.addEventListener('click', function () {
            loadHistoricalData();
        });
    }

    // Function to load historical weekly data
    function loadHistoricalData() {
        const year = yearSelect.value;
        const season = seasonSelect.value;
        const week = weekSelect.value;

        // Show loading indicator
        const loadingIndicator = document.createElement('div');
        loadingIndicator.className = 'loading';
        loadButton.appendChild(loadingIndicator);
        loadButton.disabled = true;

        // Update the title to reflect selected period
        const titleElement = document.querySelector('#weekly-ranking .card-title');
        if (titleElement) {
            titleElement.textContent = `${capitalizeFirst(season)} ${year} - Week ${week}`;
        }

        // For GitHub Pages, we'll load the JSON directly from the static directory
        const jsonPath = `/static/data/${year}/${season}/week_${week}.json`;

        fetch(jsonPath)
            .then(response => {
                if (!response.ok) {
                    throw new Error(`No data available for ${season} ${year} week ${week}`);
                }
                return response.json();
            })
            .then(data => {
                // Clear loading indicator
                loadButton.removeChild(loadingIndicator);
                loadButton.disabled = false;

                // Update the table with historical data
                updateWeeklyTable(data);

                // Update last updated timestamp
                const updateTimeElement = document.getElementById('weekly-update-time');
                if (updateTimeElement) {
                    updateTimeElement.textContent = new Date().toLocaleString();
                }
            })
            .catch(error => {
                // Handle errors
                loadButton.removeChild(loadingIndicator);
                loadButton.disabled = false;

                // Clear table and show error message
                weeklyTable.innerHTML = `
                    <tr>
                        <td colspan="5" style="text-align: center; padding: 20px;">
                            <div class="empty-state">
                                <i class="fas fa-exclamation-circle"></i>
                                <p>Data not available</p>
                                <span>${error.message}</span>
                            </div>
                        </td>
                    </tr>
                `;

                console.error('Error loading historical data:', error);
            });
    }

    // Function to update the weekly ranking table with data
    function updateWeeklyTable(data) {
        // Clear existing table content
        weeklyTable.innerHTML = '';

        // Sort data by rank
        data.sort((a, b) => a.current_rank - b.current_rank);

        // Add rows for each show
        data.forEach(show => {
            const row = document.createElement('tr');

            // Rank cell with change indicator
            let rankChangeHtml = '';
            if (show.rank_change !== 'new' && show.rank_change !== 'returning') {
                const changeClass = parseInt(show.rank_change) > 0 ? 'up' : 'down';
                rankChangeHtml = `<span class="rank-change ${changeClass}">${Math.abs(parseInt(show.rank_change))}</span>`;
            }

            row.innerHTML = `
                <td>
                    <span class="rank">${show.current_rank}</span>
                    ${rankChangeHtml}
                </td>
                <td>
                    <div class="anime-title">
                        <img src="${show.images.medium}" alt="${show.title}" class="anime-img">
                        <div class="anime-info">
                            <span class="anime-name">${show.title_english || show.title}</span>
                            <span class="episode">Episode ${show.episode}</span>
                        </div>
                    </div>
                </td>
                <td>
                    <span class="karma">${show.karma}</span>
                    ${show.karma_change !== 0 ?
                    `<span class="karma-change ${show.karma_change > 0 ? 'positive' : 'negative'}">${Math.abs(show.karma_change)}</span>`
                    : ''}
                </td>
                <td class="comments">${show.comments}</td>
                <td>
                    <div class="action-links">
                        <a href="${show.url}" class="action-link reddit-link" target="_blank">Reddit</a>
                        ${show.streams && show.streams.url ?
                    `<a href="${show.streams.url}" class="action-link stream-link" target="_blank">
                                ${show.streams.logo ?
                        `<img src="${show.streams.logo}" alt="${show.streams.service}" class="stream-logo">`
                        : 'Watch'}
                            </a>`
                    : ''}
                    </div>
                </td>
            `;

            weeklyTable.appendChild(row);
        });
    }

    // Helper function to capitalize first letter
    function capitalizeFirst(string) {
        return string.charAt(0).toUpperCase() + string.slice(1);
    }

    // Handle season change - update available weeks
    seasonSelect.addEventListener('change', function () {
        const year = yearSelect.value;
        const season = seasonSelect.value;

        // Reset week to 1 when season changes
        weekSelect.value = 1;
    });
});