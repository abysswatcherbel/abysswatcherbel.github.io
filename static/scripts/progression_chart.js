document.addEventListener("DOMContentLoaded", async function () {
    const charts = document.querySelectorAll(".progression-chart");

    try {
        const response = await fetch("static/data/progression.json");
        if (!response.ok) {
            throw new Error(`Failed to load progression data: ${response.statusText}`);
        }
        const progressionData = await response.json();

        charts.forEach(canvas => {
            // Convert the canvas data-id (a string) to a number, if needed
            const malId = parseInt(canvas.dataset.id, 10);
            const data = progressionData.find(item => item.mal_id === malId);
            
            if (!data || !data.progression) {
                console.warn(`No progression data found for mal_id: ${malId}`);
                return;
            }
            
            // Optionally, sort the progression data by hour if needed:
            data.progression.sort((a, b) => a.hour - b.hour);

            const hours = data.progression.map(p => p.hour);
            const karma = data.progression.map(p => p.karma);

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
                    devicePixelRatio: 2,
                    maintainAspectRatio: false,
                    scales: {
                        x: { type: "linear", display: false, min: 0, max: 48 },
                        y: { display: false }
                    },
                    plugins: { legend: { display: false }, tooltip: { enabled: true, intersect: false, model: "index" }}
                }
            });
        });
    } catch (error) {
        console.error("Error initializing charts:", error);
    }
});
