document.addEventListener("DOMContentLoaded", function() {
    const toggleButton = document.querySelector(".synopsis-toggle");
    const synopsisContent = document.querySelector(".synopsis-content");

    toggleButton.addEventListener("click", function() {
      if (synopsisContent.style.display === "none" || synopsisContent.style.display === "") {
        synopsisContent.style.display = "block";
        toggleButton.classList.add("active");
        toggleButton.textContent = "▲ Hide Synopsis";
      } else {
        synopsisContent.style.display = "none";
        toggleButton.classList.remove("active");
        toggleButton.textContent = "▼ Show Synopsis";
      }
    });
});

