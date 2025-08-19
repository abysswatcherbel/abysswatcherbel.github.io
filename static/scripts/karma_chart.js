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

    // Filtering state - Now with default values
    const [searchTerm, setSearchTerm] = useState('');
    const [selectedYear, setSelectedYear] = useState('');
    const [selectedSeason, setSelectedSeason] = useState('');
    const [karmaRange, setKarmaRange] = useState({ min: 0, max: Infinity });

    // Current year and season for default filter
    const getCurrentSeason = () => {
        const now = new Date();
        const month = now.getMonth();
        if (month >= 0 && month <= 2) return 'winter';
        if (month >= 3 && month <= 5) return 'spring';
        if (month >= 6 && month <= 8) return 'summer';
        return 'fall';
    };

    const getCurrentYear = () => new Date().getFullYear();

    // Color palette for different shows
    const colors = [
        "#ff6b6b", "#4ecdc4", "#6c5ce7", "#fdcb6e",
        "#e17055", "#00cec9", "#0984e3", "#fd79a8",
        "#55efc4", "#fab1a0", "#74b9ff", "#a29bfe"
    ];

    // Reset filters function
    const resetFilters = () => {
        console.log("Resetting all filters");
        setSearchTerm('');
        setSelectedYear('');
        setSelectedSeason('');
        setKarmaRange({ min: 0, max: Math.max(...availableShows.map(show => show.finalKarma)) });
    };

    // Generate a unique composite ID that includes both show ID and episode
    const generateCompositeId = (showId, episode) => {
        return `${showId}_ep${episode}`;
    };

    // Parse a composite ID back into its components
    const parseCompositeId = (compositeId) => {
        const parts = compositeId.split('_ep');
        return {
            showId: parts[0],
            episode: parts[1]
        };
    };

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

                        const rawId = String(show.mal_id || show.reddit_id);
                        const episode = show.episode || "?";
                        // Create a composite ID that includes both show ID and episode
                        const compositeId = generateCompositeId(rawId, episode);

                        return {
                            rawId: rawId,
                            id: compositeId,
                            title: show.title || show.title_english || "Unknown Title",
                            episode: episode,
                            season: show.season || getCurrentSeason(),
                            year: show.year || getCurrentYear(),
                            finalKarma: finalKarma
                        };
                    });

                    // Create a map of show data keyed by composite ID
                    const showData = {};
                    data.forEach(function (show) {
                        const rawId = String(show.mal_id || show.reddit_id);
                        const episode = show.episode || "?";
                        const compositeId = generateCompositeId(rawId, episode);

                        showData[compositeId] = show;
                        // Add ids to the show data for easier access later
                        showData[compositeId].id = compositeId;
                        showData[compositeId].rawId = rawId;
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

                    // Set default filters to current year and season
                    setSelectedYear(String(getCurrentYear()));
                    setSelectedSeason(getCurrentSeason());
                } else {
                    // If there's only one show in the JSON
                    const rawId = String(data.mal_id || data.reddit_id);
                    const episode = data.episode || "?";
                    const compositeId = generateCompositeId(rawId, episode);

                    const show = {
                        rawId: rawId,
                        id: compositeId,
                        title: data.title || data.title_english || "Unknown Title",
                        episode: episode,
                        season: data.season || getCurrentSeason(),
                        year: data.year || getCurrentYear(),
                        finalKarma: data.hourly_karma && data.hourly_karma.length > 0 ?
                            data.hourly_karma[data.hourly_karma.length - 1].karma : 0
                    };

                    setAvailableShows([show]);
                    setKarmaData({ [compositeId]: data });
                    setSelectedShows([compositeId]);
                    setKarmaRange({ min: 0, max: show.finalKarma });

                    // Set default filters to current year and season
                    setSelectedYear(String(getCurrentYear()));
                    setSelectedSeason(getCurrentSeason());
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
        console.log("Selecting show:", showId);

        setSelectedShows(prev => {
            if (prev.includes(showId)) {
                return prev.filter(prevId => prevId !== showId);
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
        // Check for the required properties first to avoid potential errors
        if (!show || !show.title) return false;

        const matchesSearch = searchTerm === '' ||
            show.title.toLowerCase().includes(searchTerm.toLowerCase());
        const matchesYear = selectedYear === '' || String(show.year) === selectedYear;
        const matchesSeason = selectedSeason === '' || show.season === selectedSeason;
        const matchesKarma = show.finalKarma >= karmaRange.min && show.finalKarma <= karmaRange.max;

        const isMatch = matchesSearch && matchesYear && matchesSeason && matchesKarma;
        return isMatch;
    });

    // Sort shows alphabetically by title, then by episode
    const sortedShows = [...filteredShows].sort((a, b) => {
        const titleCompare = a.title.localeCompare(b.title);
        if (titleCompare !== 0) return titleCompare;

        // If same title, compare episodes
        const aEp = parseInt(a.episode) || 0;
        const bEp = parseInt(b.episode) || 0;
        return aEp - bEp;
    });

    // Force sortedShows to be a NEW array every time to ensure React detects the change
    const displayedShows = [...sortedShows];


    // Check if selected shows are in filteredShows
    if (selectedShows.length > 0 && filteredShows.length > 0) {
        const selectedShowsInFiltered = selectedShows.filter(id =>
            filteredShows.some(show => show.id === id)
        );
        console.log("Selected shows in filtered:", selectedShowsInFiltered.length);
    }

    // Prepare chart data
    const prepareChartData = () => {
        const maxHours = 48; // Assuming all shows have 48 hours of data
        const chartData = [];

        // Only include shows that are both selected AND visible in the filtered list
        const showIdsForChart = selectedShows.filter(id =>
            filteredShows.some(show => show.id === id)
        );

        console.log("Shows IDs for chart:", showIdsForChart);

        // Debug logging
        if (showIdsForChart.length > 0) {
            console.log("Selected IDs:", selectedShows);
            console.log("Filtered show IDs sample:", filteredShows.slice(0, 5).map(s => s.id));

            // Verify the karmaData contains these shows
            showIdsForChart.forEach(id => {
                if (!karmaData[id]) {
                    console.error(`Missing karmaData for ID: ${id}`);
                } else if (!karmaData[id].hourly_karma) {
                    console.error(`Missing hourly_karma for ID: ${id}`);
                } else {
                    console.log(`Found valid data for ID: ${id}, title: ${karmaData[id].title}, has image: ${!!karmaData[id].images}`);
                }
            });
        }

        // Create hour slots from 1 to 48
        for (let hour = 1; hour <= maxHours; hour++) {
            const hourData = { hour };

            // Add karma for each selected show that's also in the filtered list
            showIdsForChart.forEach(id => {
                const dataForShow = karmaData[id];
                if (dataForShow && dataForShow.hourly_karma) {
                    const hourKarma = dataForShow.hourly_karma.find(k => k.hour === hour);
                    hourData[`karma_${id}`] = hourKarma ? hourKarma.karma : null;
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
        return availableShows.find(s => s.id === showId);
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
        for (let i = 2; i < hourlyData.length; i++) {
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
                        onClick: resetFilters,
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

            // Shows selection grid with alphabetical sorting
            React.createElement(
                "div",
                {
                    // Adding a key that changes when filters change to force re-render
                    key: `grid-${searchTerm}-${selectedYear}-${selectedSeason}-${karmaRange.min}-${karmaRange.max}`,
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
                filteredShows.length > 0 ? displayedShows.map(function (show, index) {
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
                                cursor: "pointer",
                                display: "flex",
                                alignItems: "center",
                                gap: "10px"
                            },
                            onClick: function () { handleShowSelection(show.id); }
                        },
                        // Show image
                        karmaData[show.id] && karmaData[show.id].images && karmaData[show.id].images.medium &&
                        React.createElement(
                            "div",
                            {
                                style: {
                                    minWidth: "50px",
                                    width: "50px",
                                    height: "70px",
                                    overflow: "hidden",
                                    borderRadius: "4px",
                                    flexShrink: 0
                                }
                            },
                            React.createElement("img", {
                                src: karmaData[show.id].images.medium,
                                alt: show.title,
                                style: {
                                    width: "100%",
                                    height: "100%",
                                    objectFit: "cover"
                                }
                            })
                        ),
                        // Show info
                        React.createElement(
                            "div",
                            { style: { flex: "1", overflow: "hidden" } },
                            React.createElement("div", {
                                style: {
                                    fontWeight: "500",
                                    whiteSpace: "nowrap",
                                    overflow: "hidden",
                                    textOverflow: "ellipsis"
                                }
                            }, show.title),
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
            { style: { height: "440px", width: "100%" } }, // Increased height to accommodate legend
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
                        label: { value: 'Hours Since Thread Creation', position: 'insideBottom', offset: -5 },
                        ticks: [0, 6, 12, 18, 24, 30, 36, 42, 48],
                        padding: { bottom: 10 }
                    }),
                    React.createElement(YAxis, {
                        label: { value: 'Karma', angle: -90, position: 'insideLeft' },
                        domain: [0, dataMax => Math.ceil(dataMax * 1.10 / 100) * 100]
                    }),
                    React.createElement(Tooltip, {
                        formatter: function (value, name) {
                            // The name is in format "karma_[compositeId]"
                            // We need to extract just the compositeId part
                            const compositeId = name.replace('karma_', '');
                            const show = findShowById(compositeId);
                            return [value, show ? show.title + ` (Ep ${show.episode})` : 'Karma'];
                        },
                        labelFormatter: function (value) { return `Hour ${value}`; }
                    }),
                    React.createElement(Legend, {
                        formatter: function (value) {
                            // The value is in format "karma_[compositeId]"
                            // We need to extract just the compositeId part
                            const compositeId = value.replace('karma_', '');
                            const show = findShowById(compositeId);
                            return show ? `${show.title} (Ep ${show.episode})` : value;
                        },
                        wrapperStyle: {
                            paddingTop: '5px',  // Add padding above the legend
                            marginTop: '5px',   // Add margin above the legend
                            position: 'relative', // Make position relative instead of absolute
                            marginBottom: '5px'            // Remove bottom positioning
                        }
                    }),
                    // Filter selectedShows to only those that exist in filteredShows
                    selectedShows
                        .filter(showId => filteredShows.some(show => show.id === showId))
                        .map(function (showId, index) {
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
                // Only show key insights for shows that are both selected AND in the filtered list
                selectedShows
                    .filter(showId => filteredShows.some(show => show.id === showId))
                    .map(function (showId, index) {
                        const show = karmaData[showId];
                        const hourlyData = show && show.hourly_karma ? show.hourly_karma : [];
                        const stats = calculateStats(hourlyData, showId);
                        const displayShow = findShowById(showId);

                        if (!stats || !displayShow) return null;

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
                                displayShow.title, " (Episode ", displayShow.episode, "):"
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
