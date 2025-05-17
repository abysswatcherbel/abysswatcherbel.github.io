document.addEventListener('DOMContentLoaded', function () {

    function waitForImages(element) {
        const imgs = element.querySelectorAll('img');
        const promises = [];
        imgs.forEach(img => {
            if (!img.complete) {
                promises.push(new Promise(resolve => {
                    img.onload = img.onerror = resolve;
                }));
            }
        });
        return Promise.all(promises);
      }
    document.getElementById('editModeBtn').onclick = function () {
        document.body.classList.toggle('edit-mode');
        const isActive = document.body.classList.contains('edit-mode');
        editModeBtn.classList.toggle('active', isActive);
        
    
    };
    document.getElementById('copyHtmlBtn').onclick = () => {
        const chart = document.querySelector('.container');
        if (!chart) return;
        navigator.clipboard.writeText(chart.outerHTML);
    };

    
});