# Anime Karma Rankings & Discussion Automation 

## Overview

The **Anime Karma Rankings** is a full-stack Python project designed to process and rank anime-related discussion posts from Reddit. It leverages the Reddit API (via PRAW), MongoDB, and external data sources (like MyAnimeList) to:

- Retrieve and process Reddit discussions made within a 48-hour window.
- Calculate weekly changes, rank shifts, and karma differences.
- Generate static pages for the current season using Flask Frozen.
- Deploy static pages to Github Pages.

This project was created to automate the tracking and ranking of anime discussions made on r/anime, a half a decade tradition, which historically was made by hand by members of the community.

## Features

- **Reddit Post Processing:**  
  Extract posts from a specified Reddit user within a 48-hour window and schedule post processing.

- **Dynamic Ranking System:**  
  Calculate weekly rankings and karma changes using MongoDB data.  
  Example functions: `get_weekly_change()`, `assign_rank()`, and `get_season_averages()`.

- **MyAnimeList Integration:**  
  Fetch statistics from MyAnimeList (MAL) via the JIKAN API with calls to update rankings with additional metadata.

- **Flask Web Application:**  
  - Dynamic endpoints for the current week (`/`) and the current chart (`/current_chart.html`).
  - Render weekly anime ranking pages and static assets using Flask Frozen for deployment on github pages.

- **Data Persistence:**  
  - MongoDB is used to store detailed post information and hourly progression data.
  - SQLite database support for alternative storage via `src/database.py`.

- **Extensive Logging & Error Handling:**  
  Robust logging configured across different modules for easier debugging and historical analysis.

## Project Structure

Here’s the corrected Markdown structure that will render properly on GitHub:

```
├── docs/                  # GitHub Pages Static Site
├── entry.py               # Main Flask application with endpoints and command-line logic
├── README.md              # This file
├── requirements.txt       # Python dependencies
├── src/
│   ├── post_processing.py # Functions for Reddit post retrieval, scheduling, and insertion into MongoDB
│   ├── rank_processing.py # Functions for ranking calculations, weekly changes, and MAL integration
│   ├── season_references/ # Season reference files, as start and end dates for each week of the season
│   │   └── 2025/
│   │       └── winter/
│   │           ├── episodes.csv      # CSV file with the start and end date for each given week of the season
│   │           ├── post.csv          # CSV file with the post id, title, and url for each post in the season
│   │           └── winter_2025.yaml  # YAML file with the season details from the r/anime mod team
│   │                                  
├── static/                # Static assets for the website
│   ├── assets/
│   │   ├── back_svg.py
│   │   ├── __init__.py
│   │   ├── new_entry.py
│   ├── css/               # CSS files for the website
│   │   ├── home.css
│   │   ├── new_karma.css
│   │   └── streaming.css
│   ├── data/              # Data files for the website
│   │   └── progression.json
│   └── scripts/           # JavaScript files for the website
│       ├── progression_chart.js
│       ├── reddit_fallback.js
│       ├── sort_tables.js
│       └── theme-switch.js
├── templates/             # Templates to be rendered by Flask
│   ├── 2024/              # Previous seasons
│   │   └── fall/
│   │       ├── week_x.html
│   │       └── week_x+1.html
│   ├── 2025/  
│   │   └── winter/
│   │       ├── week_x.html
│   │       └── week_x+1.html
│   ├── current_chart.html  # Current chart page
│   └── current_week.html   # Home page
```

 
## Recommended Projects & Resources

- **Animetrics**
    - A defuncted project that automatically tracked and created the charts posted on r/anime, which was one of the first initiatives to automate the process. The code is now open source and can be found below.
    - [GitHub Repo](https://github.com/ShaneIsrael/animetrics)
- **Anime Karma Charts**
    - The most advanced available site for viewing the ranks from r/anime discussions, with the main difference being that it doesn't have the 48-hour window cut off for discussions to be tracked, so shows will be updated regardless of when they were posted.
    - [Site](https://animekarmalist.com/)
- **r/anime GitHub**
    - The GitHub repo for the r/anime mod team, which contains many applications and resources for the community, including the season data used in this project to align the titles in the database with the ones used on reddit.
    - [GitHub Repo](https://github.com/r-anime/holo)