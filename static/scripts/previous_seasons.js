document.addEventListener('DOMContentLoaded', function () {
    // Variables to track current selections
    let activeYearElement = null;
    let activeSeasonElement = null;

    // Year click handler
    const yearItems = document.querySelectorAll('.year-item');
    console.log(`Year Items found: ${yearItems.length}`);
    yearItems.forEach(item => {
        console.log(`Year Item found: ${item.textContent}`)
        item.addEventListener('click', function (e) {
            e.stopPropagation();
            const year = this.getAttribute('data-year');
            console.log(`Year clicked: ${year}`);

            // Hide all season dropdowns first
            document.querySelectorAll('.seasons-dropdown').forEach(dropdown => {
                dropdown.style.display = 'none';
            });

            // Show seasons for this year
            const seasonsDropdown = document.getElementById(`seasons-${year}`);
            if (seasonsDropdown) {
                // Position the seasons dropdown
                const rect = this.getBoundingClientRect();
                seasonsDropdown.style.top = `${rect.top}px`;
                seasonsDropdown.style.left = `${rect.right + 5}px`;
                seasonsDropdown.style.display = 'block';
            }

            // Update active styles
            if (activeYearElement) activeYearElement.classList.remove('active');
            this.classList.add('active');
            activeYearElement = this;

            // Hide any active weeks dropdown
            if (activeSeasonElement) {
                activeSeasonElement.classList.remove('active');
                activeSeasonElement = null;
                document.querySelectorAll('.weeks-dropdown').forEach(dropdown => {
                    dropdown.style.display = 'none';
                });
            }
        });
    });

    // Season click handler
    const seasonItems = document.querySelectorAll('.season-item');
    seasonItems.forEach(item => {
        item.addEventListener('click', function (e) {
            e.stopPropagation();
            const year = this.getAttribute('data-year');
            const season = this.getAttribute('data-season');

            // Hide all weeks dropdowns first
            document.querySelectorAll('.weeks-dropdown').forEach(dropdown => {
                dropdown.style.display = 'none';
            });

            // Show weeks for this season
            const weeksDropdown = document.getElementById(`weeks-${year}-${season}`);
            if (weeksDropdown) {
                // Position the weeks dropdown
                const rect = this.getBoundingClientRect();
                weeksDropdown.style.top = `${rect.top}px`;
                weeksDropdown.style.left = `${rect.right + 5}px`;
                weeksDropdown.style.display = 'block';
            }

            // Update active styles
            if (activeSeasonElement) activeSeasonElement.classList.remove('active');
            this.classList.add('active');
            activeSeasonElement = this;
        });
    });

    // Close dropdowns when clicking elsewhere
    document.addEventListener('click', function () {
        if (activeYearElement) {
            activeYearElement.classList.remove('active');
            activeYearElement = null;

            document.querySelectorAll('.seasons-dropdown').forEach(dropdown => {
                dropdown.style.display = 'none';
            });
        }

        if (activeSeasonElement) {
            activeSeasonElement.classList.remove('active');
            activeSeasonElement = null;

            document.querySelectorAll('.weeks-dropdown').forEach(dropdown => {
                dropdown.style.display = 'none';
            });
        }
    });

    // Prevent dropdown from closing when clicking inside it
    document.querySelectorAll('.dropdown-content, .seasons-dropdown, .weeks-dropdown').forEach(element => {
        element.addEventListener('click', function (e) {
            e.stopPropagation();
        });
    });
});