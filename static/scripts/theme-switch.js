document.addEventListener("DOMContentLoaded", function() {
    const themeButton = document.getElementById("theme-button");
    const body = document.body;

    // Default to Dark Mode if no preference is set
    if (!localStorage.getItem("theme")) {
      localStorage.setItem("theme", "dark");
    }

    // Apply saved theme preference
    if (localStorage.getItem("theme") === "dark") {
      body.classList.add("dark-mode");
      themeButton.textContent = "☀️ Light Mode";
    } else {
      themeButton.textContent = "🌙 Dark Mode";
    }

    // Toggle Dark/Light Mode
    themeButton.addEventListener("click", function() {
      if (body.classList.contains("dark-mode")) {
        body.classList.remove("dark-mode");
        localStorage.setItem("theme", "light");
        themeButton.textContent = "🌙 Dark Mode";
      } else {
        body.classList.add("dark-mode");
        localStorage.setItem("theme", "dark");
        themeButton.textContent = "☀️ Light Mode";
      }
    });
  });