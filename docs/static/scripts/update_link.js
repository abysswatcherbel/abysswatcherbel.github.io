document.addEventListener('DOMContentLoaded', function () {
    const detailsDiv = document.querySelector('.details');
    const link = detailsDiv.querySelector('.external-link');

    const observer = new MutationObserver(() => {
        let style = detailsDiv.style.backgroundImage;
        let urlMatch = style.match(/url\(["']?(.*?)["']?\)/);

        if (urlMatch) {
            let newUrl = urlMatch[1];
            if (link.href !== newUrl) {
                link.href = newUrl;
            }
        }
    });

    observer.observe(detailsDiv, { attributes: true, attributeFilter: ['style'] });
});
