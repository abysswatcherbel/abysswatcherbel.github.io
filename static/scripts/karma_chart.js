// karma_chart.js - React component for karma comparison chart
const { useState, useEffect } = React;
const { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } = Recharts;

const KarmaComparisonChart = () => {
    const [availableShows, setAvailableShows] = useState([]);
    const [selectedShows, setSelectedShows] = useState([]);
    const [karmaData, setKarmaData] = useState({});
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    // Color palette for different shows
    const colors = [
        "#ff6b6b", "#4ecdc4", "#6c5ce7", "#fdcb6e",
        "#e17055", "#00cec9", "#0984e3", "#fd79a8",
        "#55efc4", "#fab1a0", "#74b9ff", "#a29bfe"
    ];

    useEffect(() => {
        async function fetchData() {
            try {
                // Fetch the JSON data
                const response = await fetch('/static/database/karma_watch.json');
                if (!response.ok) {
                    throw new Error(`Failed to fetch data: ${response.status} ${response.statusText}`);
                }

                const data = await response.json();

                // Handle the data
                if (Array.isArray(data)) {
                    // Create a list of available shows
                    const shows = data.map(show => ({
                        id: show.mal_id || show.reddit_id,
                        title: show.title,
                        episode: show.episode,
                        season: show.season,
                        year: show.year
                    }));

                    // Create a map of show data keyed by ID
                    const showData = {};
                    data.forEach(show => {
                        showData[show.mal_id || show.reddit_id] = show;
                    });

                    setAvailableShows(shows);
                    setKarmaData(showData);

                    // Auto-select the first show if available
                    if (shows.length > 0) {
                        setSelectedShows([shows[0].id]);
                    }
                } else {
                    // If there's only one show in the JSON
                    const show = {
                        id: data.mal_id || data.reddit_id,
                        title: data.title,
                        episode: data.episode,
                        season: data.season,
                        year: data.year
                    };

                    setAvailableShows([show]);
                    setKarmaData({ [show.id]: data });
                    setSelectedShows([show.id]);
                }

                setLoading(false);
            } catch (err) {
                console.error("Error fetching data:", err);
                setError(err.message || "Failed to load data");
                setLoading(false);
            }
        }

        fetchData();
    }, []);

    // Handle show selection changes
    const handleShowSelection = (showId) => {
        setSelectedShows(prev => {
            if (prev.includes(showId)) {
                return prev.filter(id => id !== showId);
            } else {
                return [...prev, showId];
            }
        });
    };

    // Prepare chart data
    const prepareChartData = () => {
        const maxHours = 48; // Assuming all shows have 48 hours of data
        const chartData = [];

        // Create hour slots from 1 to 48
        for (let hour = 1; hour <= maxHours; hour++) {
            const hourData = { hour };

            // Add karma for each selected show
            selectedShows.forEach(showId => {
                const show = karmaData[showId];
                if (show && show.hourly_karma) {
                    const hourKarma = show.hourly_karma.find(k => k.hour === hour);
                    hourData[`karma_${showId}`] = hourKarma ? hourKarma.karma : null;
                }
            });

            chartData.push(hourData);
        }

        return chartData;
    };

    if (loading) {
        return <div className="loading-message">Loading karma data...</div>;
    }

    if (error) {
        return <div className="error-message">Error: {error}</div>;
    }

    const chartData = prepareChartData();

    return (
        <div>
            <div style={{ marginBottom: "24px" }}>
                <h3 style={{ marginBottom: "12px", fontWeight: "600" }}>Select Shows to Compare:</h3>
                <div style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(auto-fill, minmax(250px, 1fr))",
                    gap: "8px"
                }}>
                    {availableShows.map((show, index) => (
                        <div
                            key={show.id}
                            style={{
                                padding: "8px",
                                border: "1px solid",
                                borderColor: selectedShows.includes(show.id) ? "#3b82f6" : "#d1d5db",
                                borderRadius: "6px",
                                backgroundColor: selectedShows.includes(show.id) ? "rgba(59, 130, 246, 0.1)" : "transparent",
                                cursor: "pointer"
                            }}
                            onClick={() => handleShowSelection(show.id)}
                        >
                            <div style={{ fontWeight: "500" }}>{show.title}</div>
                            <div style={{ fontSize: "0.875rem", opacity: "0.8" }}>
                                Episode {show.episode} ({show.season} {show.year})
                            </div>
                        </div>
                    ))}
                </div>
            </div>

            <div style={{ height: "400px", width: "100%" }}>
                <ResponsiveContainer width="100%" height="100%">
                    <LineChart
                        data={chartData}
                        margin={{ top: 20, right: 30, left: 20, bottom: 20 }}
                    >
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis
                            dataKey="hour"
                            label={{ value: 'Hours Since Thread Creation', position: 'insideBottom', offset: -10 }}
                            ticks={[0, 6, 12, 18, 24, 30, 36, 42, 48]}
                        />
                        <YAxis
                            label={{ value: 'Karma', angle: -90, position: 'insideLeft' }}
                            domain={[0, 'dataMax + 10']}
                        />
                        <Tooltip
                            formatter={(value, name) => {
                                const showId = name.split('_')[1];
                                const show = availableShows.find(s => s.id.toString() === showId);
                                return [value, show ? show.title : 'Karma'];
                            }}
                            labelFormatter={(value) => `Hour ${value}`}
                        />
                        <Legend
                            formatter={(value) => {
                                const showId = value.split('_')[1];
                                const show = availableShows.find(s => s.id.toString() === showId);
                                return show ? `${show.title} (Ep ${show.episode})` : value;
                            }}
                        />

                        {selectedShows.map((showId, index) => (
                            <Line
                                key={showId}
                                type="monotone"
                                dataKey={`karma_${showId}`}
                                stroke={colors[index % colors.length]}
                                strokeWidth={2}
                                name={`karma_${showId}`}
                                dot={{ r: 1 }}
                                activeDot={{ r: 5 }}
                                connectNulls
                            />
                        ))}
                    </LineChart>
                </ResponsiveContainer>
            </div>

            {selectedShows.length > 0 && (
                <div style={{
                    marginTop: "24px",
                    padding: "16px",
                    backgroundColor: "rgba(0, 0, 0, 0.05)",
                    borderRadius: "8px"
                }}>
                    <h3 style={{ marginBottom: "12px", fontWeight: "600" }}>Key Insights:</h3>
                    <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
                        {selectedShows.map((showId, index) => {
                            const show = karmaData[showId];
                            const hourlyData = show.hourly_karma || [];

                            if (hourlyData.length === 0) return null;

                            const startKarma = hourlyData.find(k => k.hour === 1)?.karma || 0;
                            const endKarma = hourlyData.find(k => k.hour === 48)?.karma ||
                                hourlyData[hourlyData.length - 1]?.karma || 0;
                            const maxKarma = Math.max(...hourlyData.map(item => item.karma));
                            const karmaGrowth = endKarma - startKarma;
                            const growthPercentage = startKarma > 0 ? ((endKarma / startKarma) * 100 - 100).toFixed(1) : "N/A";

                            return (
                                <div key={showId} style={{
                                    borderLeft: `4px solid ${colors[index % colors.length]}`,
                                    paddingLeft: "12px"
                                }}>
                                    <h4 style={{ fontWeight: "600", marginBottom: "8px" }}>{show.title} (Episode {show.episode}):</h4>
                                    <ul style={{ listStyleType: "disc", paddingLeft: "24px", margin: 0 }}>
                                        <li>Starting karma: {startKarma}</li>
                                        <li>Final karma: {endKarma}</li>
                                        <li>Total growth: {karmaGrowth} points ({growthPercentage}%)</li>
                                        <li>Peak karma: {maxKarma}</li>
                                    </ul>
                                </div>
                            );
                        })}
                    </div>
                </div>
            )}
        </div>
    );
};

// Render the component
ReactDOM.render(
    <KarmaComparisonChart />,
    document.getElementById('karma-chart')
);