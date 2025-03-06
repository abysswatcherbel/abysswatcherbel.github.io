// Karma Progression Comparison Integration

document.addEventListener('DOMContentLoaded', () => {
    // Add the tab for karma comparison
    addKarmaComparisonTab();
    
    // Initialize the tab functionality
    initializeTabs();
    
    // Load the karma progression data
    loadKarmaProgressionData();
  });
  
  function addKarmaComparisonTab() {
    // Add tab button to the tab navigation
    const tabsNav = document.querySelector('.tabs-nav');
    if (!tabsNav) return;
    
    const karmaComparisonTab = document.createElement('button');
    karmaComparisonTab.className = 'tab-button';
    karmaComparisonTab.setAttribute('data-tab', 'karma-comparison');
    karmaComparisonTab.innerHTML = '<i class="fas fa-chart-line"></i> Karma Comparison';
    
    tabsNav.appendChild(karmaComparisonTab);
    
    // Add tab content container
    const tabsContainer = document.querySelector('.tabs-container');
    if (!tabsContainer) return;
    
    const karmaComparisonContent = document.createElement('div');
    karmaComparisonContent.className = 'tab-content';
    karmaComparisonContent.id = 'karma-comparison';
    
    // Add a placeholder that will be replaced with the React component
    karmaComparisonContent.innerHTML = `
      <div id="karma-comparison-container">
        <div class="loading">Loading karma comparison data...</div>
      </div>
    `;
    
    tabsContainer.appendChild(karmaComparisonContent);
  }
  
  function initializeTabs() {
    // Get all tab buttons and tab content
    const tabButtons = document.querySelectorAll('.tab-button');
    const tabContents = document.querySelectorAll('.tab-content');
    
    // Add click event to tab buttons
    tabButtons.forEach(button => {
      button.addEventListener('click', () => {
        // Remove active class from all buttons and contents
        tabButtons.forEach(btn => btn.classList.remove('active'));
        tabContents.forEach(content => content.classList.remove('active'));
        
        // Add active class to clicked button
        button.classList.add('active');
        
        // Show corresponding tab content
        const tabId = button.getAttribute('data-tab');
        const tabContent = document.getElementById(tabId);
        if (tabContent) {
          tabContent.classList.add('active');
        }
      });
    });
  }
  
  async function loadKarmaProgressionData() {
    try {
      // Fetch progression data
      const response = await fetch('/static/data/progression.json');
      if (!response.ok) {
        throw new Error('Failed to load progression data');
      }
      
      const progressionData = await response.json();
      
      // Fetch active discussions to get show titles
      const activeResponse = await fetch('/api/active-discussions');
      if (!activeResponse.ok) {
        throw new Error('Failed to load active discussions');
      }
      
      const activeDiscussions = await activeResponse.json();
      
      // Map progression data with show titles from active discussions
      const showsWithTitles = progressionData.map(show => {
        const activeShow = activeDiscussions.find(active => active.mal_id === show.mal_id);
        return {
          ...show,
          title: activeShow ? (activeShow.title_english || activeShow.title) : `Show ${show.mal_id}`,
          episode: activeShow ? activeShow.episode : 'Unknown'
        };
      });
      
      // Render the checkboxes and chart container
      renderKarmaComparisonUI(showsWithTitles);
      
    } catch (error) {
      console.error('Error loading karma progression data:', error);
      const container = document.getElementById('karma-comparison-container');
      if (container) {
        container.innerHTML = `
          <div class="error-message">
            <p>Error loading karma comparison data. Please try again later.</p>
          </div>
        `;
      }
    }
  }
  
  function renderKarmaComparisonUI(shows) {
    const container = document.getElementById('karma-comparison-container');
    if (!container) return;
    
    // Create the container for the feature
    container.innerHTML = `
      <div class="card">
        <div class="card-header">
          <h2 class="card-title">Karma Progression Comparison</h2>
          <p class="card-subtitle">Select up to 5 shows to compare their karma progression over time</p>
        </div>
        
        <div class="show-selection">
          <div class="selection-header">
            <h3>Select Shows to Compare</h3>
            <button id="clear-selection" class="clear-selection" style="display: none;">
              Clear All
            </button>
          </div>
          
          <div class="show-checkboxes" id="show-checkboxes">
            ${shows.map(show => `
              <div class="show-checkbox">
                <input type="checkbox" id="show-${show.mal_id}" class="show-selector" data-mal-id="${show.mal_id}" data-title="${show.title}">
                <label for="show-${show.mal_id}">
                  ${show.title} ${show.episode ? `(Ep ${show.episode})` : ''}
                </label>
              </div>
            `).join('')}
          </div>
        </div>
        
        <div id="chart-container" class="chart-container" style="display: none;">
          <canvas id="karma-chart"></canvas>
        </div>
        
        <div id="no-selection" class="no-selection">
          <p>Please select shows to compare their karma progression</p>
        </div>
      </div>
    `;
    
    // Initialize chart and checkboxes
    initializeKarmaComparison(shows);
  }
  
  function initializeKarmaComparison(shows) {
    const checkboxes = document.querySelectorAll('.show-selector');
    const clearButton = document.getElementById('clear-selection');
    const chartContainer = document.getElementById('chart-container');
    const noSelection = document.getElementById('no-selection');
    
    // Colors for different shows
    const colors = [
      'rgb(136, 132, 216)', 'rgb(130, 202, 157)', 'rgb(255, 198, 88)', 
      'rgb(255, 128, 66)', 'rgb(0, 136, 254)', 'rgb(0, 196, 159)', 
      'rgb(255, 187, 40)', 'rgb(255, 128, 66)', 'rgb(164, 222, 108)', 
      'rgb(208, 237, 87)'
    ];
    
    let selectedShows = [];
    let chart = null;
    
    // Initialize Chart.js
    function createChart() {
      const ctx = document.getElementById('karma-chart').getContext('2d');
      
      // Create or update chart with selected shows data
      if (chart) {
        chart.destroy();
      }
      
      // Prepare data for the chart
      const datasets = selectedShows.map((showId, index) => {
        const show = shows.find(s => s.mal_id === showId);
        const color = colors[index % colors.length];
        
        return {
          label: show.title,
          data: show.progression.map(p => ({
            x: p.hour,
            y: p.karma
          })),
          borderColor: color,
          backgroundColor: color + '20', // 20% opacity
          pointBackgroundColor: color,
          tension: 0.1,
          fill: false
        };
      });
      
      chart = new Chart(ctx, {
        type: 'line',
        data: {
          datasets: datasets
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          scales: {
            x: {
              type: 'linear',
              title: {
                display: true,
                text: 'Hours Since Post'
              },
              ticks: {
                stepSize: 4
              }
            },
            y: {
              title: {
                display: true,
                text: 'Karma'
              },
              beginAtZero: true
            }
          },
          plugins: {
            tooltip: {
              callbacks: {
                title: function(tooltipItems) {
                  return tooltipItems[0].parsed.x + ' hours';
                },
                label: function(context) {
                  return context.dataset.label + ': ' + context.parsed.y + ' karma';
                }
              }
            }
          }
        }
      });
    }
    
    // Handle checkbox selection
    checkboxes.forEach(checkbox => {
      checkbox.addEventListener('change', function() {
        const malId = parseInt(this.getAttribute('data-mal-id'));
        const title = this.getAttribute('data-title');
        
        if (this.checked) {
          // Add to selected shows (limit to 5)
          if (selectedShows.length < 5) {
            selectedShows.push(malId);
            
            // Style the label with the show's color
            const colorIndex = selectedShows.indexOf(malId) % colors.length;
            const label = document.querySelector(`label[for="show-${malId}"]`);
            if (label) {
              label.style.borderLeft = `4px solid ${colors[colorIndex]}`;
              label.style.paddingLeft = '10px';
            }
          } else {
            // Uncheck if we've reached the limit
            this.checked = false;
            alert('You can select a maximum of 5 shows to compare');
          }
        } else {
          // Remove from selected shows
          selectedShows = selectedShows.filter(id => id !== malId);
          
          // Reset label style
          const label = document.querySelector(`label[for="show-${malId}"]`);
          if (label) {
            label.style.borderLeft = '4px solid transparent';
          }
        }
        
        // Update UI based on selection
        if (selectedShows.length > 0) {
          chartContainer.style.display = 'block';
          noSelection.style.display = 'none';
          clearButton.style.display = 'block';
          createChart();
        } else {
          chartContainer.style.display = 'none';
          noSelection.style.display = 'flex';
          clearButton.style.display = 'none';
        }
      });
    });
    
    // Clear selection button
    clearButton.addEventListener('click', function() {
      selectedShows = [];
      checkboxes.forEach(checkbox => {
        checkbox.checked = false;
        
        // Reset all label styles
        const label = document.querySelector(`label[for="${checkbox.id}"]`);
        if (label) {
          label.style.borderLeft = '4px solid transparent';
        }
      });
      
      chartContainer.style.display = 'none';
      noSelection.style.display = 'flex';
      clearButton.style.display = 'none';
    });
  }