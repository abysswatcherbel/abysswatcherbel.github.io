// karma_chart.js - React component for karma comparison chart
const { useState, useEffect } = React;
const { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } = window.Recharts;

// Setting up the component to fetch data and render the chart
const KarmaComparisonChart = () => {
    const [availableShows, setAvailableShows] = useState([]);
    const [selectedShows, setSelectedShows] = useState([]);
    const [karmaData, setKarmaData] = useState({});
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    // Filtering state
    const [searchTerm, setSearchTerm] = useState('');
    const [selectedYear, setSelectedYear] = useState('');
    const [selectedSeason, setSelectedSeason] = useState('');
    const [karmaRange, setKarmaRange] = useState({ min: 0, max: Infinity });

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
                console.log("Fetching karma data...");
                const response = await fetch('static/data/karma_watch.json');
                if (!response.ok) {
                    throw new Error(`Failed to fetch data: ${response.status} ${response.statusText}`);
                }

                const data = await response.json();
                console.log("Fetched data:", data);

                // Handle the data
                if (Array.isArray(data)) {
                    // Create a list of available shows
                    const shows = data.map(function (show) {
                        // Calculate final karma for filtering
                        let finalKarma = 0;
                        if (show.hourly_karma && show.hourly_karma.length > 0) {
                            const hour48Data = show.hourly_karma.find(k => k.hour === 48);
                            if (hour48Data) {
                                finalKarma = hour48Data.karma;
                            } else {
                                finalKarma = show.hourly_karma[show.hourly_karma.length - 1].karma;
                            }
                        }

                        return {
                            id: show.mal_id || show.reddit_id,
                            title: show.title,
                            episode: show.episode,
                            season: show.season,
                            year: show.year,
                            finalKarma: finalKarma
                        };
                    });

                    // Create a map of show data keyed by ID
                    const showData = {};
                    data.forEach(function (show) {
                        showData[show.mal_id || show.reddit_id] = show;
                    });

                    setAvailableShows(shows);
                    setKarmaData(showData);

                    // Auto-select the first show if available
                    if (shows.length > 0) {
                        setSelectedShows([shows[0].id]);
                    }

                    // Set initial karma range based on data
                    const maxKarma = Math.max(...shows.map(show => show.finalKarma));
                    setKarmaRange({ min: 0, max: maxKarma });
                } else {
                    // If there's only one show in the JSON
                    const show = {
                        id: data.mal_id || data.reddit_id,
                        title: data.title,
                        episode: data.episode,
                        season: data.season,
                        year: data.year,
                        finalKarma: data.hourly_karma[data.hourly_karma.length - 1].karma || 0
                    };

                    setAvailableShows([show]);
                    setKarmaData({ [show.id]: data });
                    setSelectedShows([show.id]);
                    setKarmaRange({ min: 0, max: show.finalKarma });
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
        setSelectedShows(function (prev) {
            if (prev.includes(showId)) {
                return prev.filter(function (id) { return id !== showId; });
            } else {
                return [...prev, showId];
            }
        });
    };

    // Extract unique years and seasons for filters
    const years = [...new Set(availableShows.map(show => show.year))].sort((a, b) => b - a);
    const seasons = [...new Set(availableShows.map(show => show.season))].sort();

    // Filter shows based on search and filters
    const filteredShows = availableShows.filter(show => {
        const matchesSearch = searchTerm === '' ||
            show.title.toLowerCase().includes(searchTerm.toLowerCase());
        const matchesYear = selectedYear === '' || show.year.toString() === selectedYear;
        const matchesSeason = selectedSeason === '' || show.season === selectedSeason;
        const matchesKarma = show.finalKarma >= karmaRange.min && show.finalKarma <= karmaRange.max;

        return matchesSearch && matchesYear && matchesSeason && matchesKarma;
    });

    // Prepare chart data
    const prepareChartData = () => {
        const maxHours = 48; // Assuming all shows have 48 hours of data
        const chartData = [];

        // Create hour slots from 1 to 48
        for (let hour = 1; hour <= maxHours; hour++) {
            const hourData = { hour };

            // Add karma for each selected show
            selectedShows.forEach(function (showId) {
                const show = karmaData[showId];
                if (show && show.hourly_karma) {
                    const hourKarma = show.hourly_karma.find(function (k) { return k.hour === hour; });
                    hourData[`karma_${showId}`] = hourKarma ? hourKarma.karma : null;
                }
            });

            chartData.push(hourData);
        }

        return chartData;
    };

    if (loading) {
        return React.createElement("div", { className: "loading-message" }, "Loading karma data...");
    }

    if (error) {
        return React.createElement("div", { className: "error-message" }, "Error: ", error);
    }

    const chartData = prepareChartData();

    // Find show by ID helper function
    const findShowById = (showId) => {
        return availableShows.find(function (s) { return s.id.toString() === showId.toString(); });
    };

    // Calculate stats safely
    const calculateStats = (hourlyData, showId) => {
        if (!hourlyData || hourlyData.length === 0) {
            return null;
        }

        // Find start karma (hour 1)
        let startKarma = 0;
        for (let i = 0; i < hourlyData.length; i++) {
            if (hourlyData[i].hour === 1) {
                startKarma = hourlyData[i].karma;
                break;
            }
        }

        // Find end karma (hour 48 or last available)
        let endKarma = 0;
        for (let i = 0; i < hourlyData.length; i++) {
            if (hourlyData[i].hour === 48) {
                endKarma = hourlyData[i].karma;
                break;
            }
        }

        // If we didn't find hour 48, use the last entry
        if (endKarma === 0 && hourlyData.length > 0) {
            endKarma = hourlyData[hourlyData.length - 1].karma;
        }

        // Calculate max karma in a single hour (not cumulative max)
        let maxHourlyKarma = 0;
        let maxHourlyKarmaHour = 0;
        for (let i = 1; i < hourlyData.length; i++) {
            const prevHour = hourlyData.find(h => h.hour === hourlyData[i].hour - 1);
            const currentHour = hourlyData[i];

            if (prevHour) {
                const hourlyGain = currentHour.karma - prevHour.karma;
                if (hourlyGain > maxHourlyKarma) {
                    maxHourlyKarma = hourlyGain;
                    maxHourlyKarmaHour = currentHour.hour;
                }
            }
        }

        // Calculate growth
        const karmaGrowth = endKarma - startKarma;
        let growthPercentage = "N/A";
        if (startKarma > 0) {
            growthPercentage = ((endKarma / startKarma) * 100 - 100).toFixed(1);
        }

        return {
            startKarma: startKarma,
            endKarma: endKarma,
            maxHourlyKarma: maxHourlyKarma,
            maxHourlyKarmaHour: maxHourlyKarmaHour,
            karmaGrowth: karmaGrowth,
            growthPercentage: growthPercentage
        };
    };

    return React.createElement(
        "div",
        null,
        React.createElement(
            "div",
            { style: { marginBottom: "24px" } },
            React.createElement("h3", { style: { marginBottom: "12px", fontWeight: "600" } }, "Filter Shows:"),

            // Search and filter controls
            React.createElement(
                "div",
                {
                    style: {
                        display: "flex",
                        flexWrap: "wrap",
                        gap: "12px",
                        marginBottom: "20px"
                    }
                },
                // Search input
                React.createElement(
                    "div",
                    { style: { flex: "1", minWidth: "200px" } },
                    React.createElement("input", {
                        type: "text",
                        placeholder: "Search by title...",
                        value: searchTerm,
                        onChange: (e) => setSearchTerm(e.target.value),
                        style: {
                            width: "100%",
                            padding: "8px",
                            borderRadius: "4px",
                            border: "1px solid #d1d5db"
                        }
                    })
                ),

                // Year filter
                React.createElement(
                    "div",
                    { style: { width: "120px" } },
                    React.createElement(
                        "select",
                        {
                            value: selectedYear,
                            onChange: (e) => setSelectedYear(e.target.value),
                            style: {
                                width: "100%",
                                padding: "8px",
                                borderRadius: "4px",
                                border: "1px solid #d1d5db"
                            }
                        },
                        React.createElement("option", { value: "" }, "All Years"),
                        years.map(year =>
                            React.createElement("option", { key: year, value: year }, year)
                        )
                    )
                ),

                // Season filter
                React.createElement(
                    "div",
                    { style: { width: "120px" } },
                    React.createElement(
                        "select",
                        {
                            value: selectedSeason,
                            onChange: (e) => setSelectedSeason(e.target.value),
                            style: {
                                width: "100%",
                                padding: "8px",
                                borderRadius: "4px",
                                border: "1px solid #d1d5db"
                            }
                        },
                        React.createElement("option", { value: "" }, "All Seasons"),
                        seasons.map(season =>
                            React.createElement("option", { key: season, value: season }, season)
                        )
                    )
                ),

                // Reset filters button
                React.createElement(
                    "button",
                    {
                        onClick: () => {
                            setSearchTerm('');
                            setSelectedYear('');
                            setSelectedSeason('');
                            setKarmaRange({ min: 0, max: Math.max(...availableShows.map(show => show.finalKarma)) });
                        },
                        style: {
                            padding: "8px 16px",
                            backgroundColor: "#f3f4f6",
                            border: "1px solid #d1d5db",
                            borderRadius: "4px",
                            cursor: "pointer"
                        }
                    },
                    "Reset Filters"
                )
            ),

            // Shows selection grid
            React.createElement(
                "div",
                {
                    style: {
                        display: "grid",
                        gridTemplateColumns: "repeat(auto-fill, minmax(250px, 1fr))",
                        gap: "8px",
                        maxHeight: "300px",
                        overflowY: "auto",
                        padding: "8px",
                        border: "1px solid #e5e7eb",
                        borderRadius: "6px"
                    }
                },
                filteredShows.length > 0 ? filteredShows.map(function (show, index) {
                    return React.createElement(
                        "div",
                        {
                            key: show.id,
                            style: {
                                padding: "8px",
                                border: "1px solid",
                                borderColor: selectedShows.includes(show.id) ? "#3b82f6" : "#d1d5db",
                                borderRadius: "6px",
                                backgroundColor: selectedShows.includes(show.id) ? "rgba(59, 130, 246, 0.1)" : "transparent",
                                cursor: "pointer"
                            },
                            onClick: function () { handleShowSelection(show.id); }
                        },
                        React.createElement("div", { style: { fontWeight: "500" } }, show.title),
                        React.createElement(
                            "div",
                            { style: { fontSize: "0.875rem", opacity: "0.8" } },
                            "Episode ", show.episode, " (", show.season, " ", show.year, ")"
                        ),
                        React.createElement(
                            "div",
                            { style: { fontSize: "0.75rem", opacity: "0.7" } },
                            "Final Karma: ", show.finalKarma.toLocaleString()
                        )
                    );
                }) : React.createElement("div", { style: { padding: "12px", textAlign: "center" } }, "No shows match your filters")
            ),

            // Selected shows count
            selectedShows.length > 0 && React.createElement(
                "div",
                { style: { marginTop: "12px", fontSize: "0.875rem" } },
                "Selected: ", selectedShows.length, " show", selectedShows.length !== 1 ? "s" : ""
            )
        ),

        React.createElement(
            "div",
            { style: { height: "400px", width: "100%" } },
            React.createElement(
                ResponsiveContainer,
                { width: "100%", height: "100%" },
                React.createElement(
                    LineChart,
                    {
                        data: chartData,
                        margin: { top: 20, right: 30, left: 20, bottom: 20 }
                    },
                    React.createElement(CartesianGrid, { strokeDasharray: "3 3" }),
                    React.createElement(XAxis, {
                        dataKey: "hour",
                        label: { value: 'Hours Since Thread Creation', position: 'insideBottom', offset: -10 },
                        ticks: [0, 6, 12, 18, 24, 30, 36, 42, 48]
                    }),
                    React.createElement(YAxis, {
                        label: { value: 'Karma', angle: -90, position: 'insideLeft' },
                        domain: [0, 'dataMax + 10']
                    }),
                    React.createElement(Tooltip, {
                        formatter: function (value, name) {
                            const showId = name.split('_')[1];
                            const show = findShowById(showId);
                            return [value, show ? show.title : 'Karma'];
                        },
                        labelFormatter: function (value) { return `Hour ${value}`; }
                    }),
                    React.createElement(Legend, {
                        formatter: function (value) {
                            const showId = value.split('_')[1];
                            const show = findShowById(showId);
                            return show ? `${show.title} (Ep ${show.episode})` : value;
                        }
                    }),
                    selectedShows.map(function (showId, index) {
                        return React.createElement(Line, {
                            key: showId,
                            type: "monotone",
                            dataKey: `karma_${showId}`,
                            stroke: colors[index % colors.length],
                            strokeWidth: 2,
                            name: `karma_${showId}`,
                            dot: { r: 1 },
                            activeDot: { r: 5 },
                            connectNulls: true
                        });
                    })
                )
            )
        ),

        selectedShows.length > 0 && React.createElement(
            "div",
            {
                style: {
                    marginTop: "24px",
                    padding: "16px",
                    backgroundColor: "rgba(0, 0, 0, 0.05)",
                    borderRadius: "8px"
                }
            },
            React.createElement("h3", { style: { marginBottom: "12px", fontWeight: "600" } }, "Key Insights:"),
            React.createElement(
                "div",
                { style: { display: "flex", flexDirection: "column", gap: "16px" } },
                selectedShows.map(function (showId, index) {
                    const show = karmaData[showId];
                    const hourlyData = show && show.hourly_karma ? show.hourly_karma : [];
                    const stats = calculateStats(hourlyData, showId);

                    if (!stats) return null;

                    return React.createElement(
                        "div",
                        {
                            key: showId,
                            style: {
                                borderLeft: `4px solid ${colors[index % colors.length]}`,
                                paddingLeft: "12px"
                            }
                        },
                        React.createElement(
                            "h4",
                            { style: { fontWeight: "600", marginBottom: "8px" } },
                            show.title, " (Episode ", show.episode, "):"
                        ),
                        React.createElement(
                            "ul",
                            { style: { listStyleType: "disc", paddingLeft: "24px", margin: 0 } },
                            React.createElement("li", null, "Starting karma: ", stats.startKarma),
                            React.createElement("li", null, "Final karma: ", stats.endKarma),
                            React.createElement("li", null, "Total growth: ", stats.karmaGrowth, " points (", stats.growthPercentage, "%)"),
                            stats.maxHourlyKarma > 0 && React.createElement(
                                "li",
                                null,
                                "Max karma gain in a single hour: ",
                                stats.maxHourlyKarma,
                                " (hour ",
                                stats.maxHourlyKarmaHour,
                                ")"
                            )
                        )
                    );
                })
            )
        )
    );
};

// Render the component
ReactDOM.render(
    React.createElement(KarmaComparisonChart, null),
    document.getElementById('karma-chart')
);