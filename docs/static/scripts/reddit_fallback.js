document.addEventListener("DOMContentLoaded", () => {
    // Only process fallback links
    document.querySelectorAll("a.external-link[data-check-fallback='true']").forEach(link => {
  
      link.addEventListener("click", event => {
        event.preventDefault();
  
        // If href is "#" or empty, we know there's no valid URL
        if (!link.href || link.getAttribute('href') === '#') {
          const query = encodeURIComponent(link.dataset.titleEnglish);
          window.open(`https://www.reddit.com/r/anime/search/?q=${query}`, "_blank");
          return;
        }
  
        // Otherwise, do the HEAD request
        fetch(link.href, { method: "HEAD" })
          .then(response => {
            if (response.ok) {
              // If URL is good, open it
              window.open(link.href, "_blank");
            } else {
              // Otherwise fallback
              const query = encodeURIComponent(link.dataset.titleEnglish);
              window.open(`https://www.reddit.com/r/anime/search/?q=${query}`, "_blank");
            }
          })
          .catch(() => {
            // On network or CORS error, fallback
            const query = encodeURIComponent(link.dataset.titleEnglish);
            window.open(`https://www.reddit.com/r/anime/search/?q=${query}`, "_blank");
          });
      });
    });
  });
  