document.addEventListener("DOMContentLoaded", () => {
    const tables = document.querySelectorAll("table.sortable");
  
    tables.forEach(table => {
      const headers = table.querySelectorAll("th");
      const tbody = table.querySelector("tbody");
      let sortedColumn = null;
      let sortDirection = 1; // 1 for ascending, -1 for descending
  
      headers.forEach((header, index) => {
        header.addEventListener("click", () => {
          if (sortedColumn === index) {
            sortDirection *= -1; // Toggle direction
          } else {
            sortedColumn = index;
            sortDirection = 1; // Default to ascending for new column
          }
  
          // Remove sorting indicators from all headers
          headers.forEach(h => h.classList.remove("sorted-asc", "sorted-desc"));
  
          // Add appropriate indicator to the clicked header
          header.classList.add(sortDirection === 1 ? "sorted-asc" : "sorted-desc");
  
          const rows = Array.from(tbody.rows);
          rows.sort((rowA, rowB) => {
            const a = rowA.cells[index].textContent.trim();
            const b = rowB.cells[index].textContent.trim();
            let comparison = 0;
  
            // Handle numeric sorting
            const numA = Number(a);
            const numB = Number(b);
  
            if (!isNaN(numA) && !isNaN(numB)) {
              comparison = (numA - numB) * sortDirection;
            } else {
              comparison = a.localeCompare(b) * sortDirection; // String comparison
            }
  
            return comparison;
          });
  
          tbody.innerHTML = ""; // Clear existing rows
          rows.forEach(row => tbody.appendChild(row)); // Re-add sorted rows
        });
      });
    });
  });
  