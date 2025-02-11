document.addEventListener("DOMContentLoaded", async function () {
    const charts = document.querySelectorAll(".progression-chart");

    try {
        const response = await fetch("src/season_references/2025/winter/progression_data/progression.json");

        if (!response.ok) {
            throw new Error(`Failed to load progression data: ${response.statusText}`);
        }

        const progressionData = await response.json();

        charts.forEach(canvas => {
            const malId = canvas.dataset.id;
            const data = progressionData.find(item => item.mal_id == malId);
            
            if (!data || !data.progression) {
                console.warn(`No progression data for mal_id: ${malId}`);
                return;
            }

            // Extract arrays for hours and karma
            const hours = data.progression.map(p => p.hour);
            const karma = data.progression.map(p => p.karma);

            // Create the chart on the canvas
            new Chart(canvas.getContext("2d"), {
                type: "line",
                data: {
                    labels: hours,
                    datasets: [{
                        label: "Karma",
                        data: karma,
                        borderColor: "#007bff",
                        borderWidth: 1.5,
                        pointRadius: 0,
                        fill: false
                    }]
                },
                options: {
                    responsive: false,
                    maintainAspectRatio: false,
                    scales: {
                        x: { display: false },
                        y: { display: false }
                    },
                    plugins: { legend: { display: false } }
                }
            });
        });
    } catch (error) {
        console.error("Error initializing charts:", error);
    }
});
