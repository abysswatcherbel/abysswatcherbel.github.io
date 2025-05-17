document.addEventListener('DOMContentLoaded', function () {
    // Modal and control elements
    const modal = document.getElementById('bannerEditorModal');
    const modalCloseButton = document.querySelector('.modal-close-button');
    const cancelBannerChangesButton = document.getElementById('cancelBannerChanges');
    const saveBannerChangesButton = document.getElementById('saveBannerChanges');
    const copyBannerCssBtn = document.getElementById('copyBannerCss');

    const imageUrlInput = document.getElementById('imageUrlInput');
    const bgPositionInput = document.getElementById('bgPositionInput');
    const bgSizeInput = document.getElementById('bgSizeInput');

    //const previewEditsToggle = document.getElementById('previewEditsToggle');
    const imagePreviewBox = document.getElementById('imagePreviewBox');
    const previewBackgroundLayer = document.getElementById('previewBackgroundLayer');
    const previewForegroundLayer = document.getElementById('previewForegroundLayer');

    // Zoom buttons
    const zoomInBtn = document.getElementById('zoomInBtn');
    const zoomOutBtn = document.getElementById('zoomOutBtn');

    let currentEditingDetailsDiv = null;
    let naturalImageWidth = 0;
    let naturalImageHeight = 0;
    let isDragging = false;
    let dragStartX, dragStartY;
    let initialBgPosX, initialBgPosY;
    let currentImageScalePercentageWidth = 100.0;
    let currentImageScaleForZoom = 1.0;

    function openModal(detailsDiv) {
        currentEditingDetailsDiv = detailsDiv;
        const style = window.getComputedStyle(detailsDiv);
        let currentUrl = style.backgroundImage.slice(5, -2).replace(/'|"/g, "");
        if (currentUrl === 'none' || !currentUrl) currentUrl = '';

        imageUrlInput.value = currentUrl;


        let initialSize = detailsDiv.style.backgroundSize; // Check inline style first
        let initialPosition = detailsDiv.style.backgroundPosition;

        // If inline styles were empty, computedStyle gives the actual applied value 
        if (!initialSize) initialSize = style.backgroundSize;
        if (!initialPosition) initialPosition = style.backgroundPosition;

        // Set initial values for inputs, then try to load image for dimensions
        bgSizeInput.value = initialSize;
        bgPositionInput.value = initialPosition;

        // Reset zoom scale for the new image context
        currentImageScaleForZoom = 1.0;

        loadImageForPreview(currentUrl, true); // true to indicate initial load
        modal.style.display = 'block';
    }

    function closeModal() {
        modal.style.display = 'none';
        currentEditingDetailsDiv = null;
        naturalImageWidth = 0; 
        naturalImageHeight = 0;

        // Reset Dragging state if modal is closed mid-drag
        imagePreviewBox.classList.remove('dragging', 'draggable');
        document.removeEventListener('mousemove', handleDragMove); // Clean up listeners
        document.removeEventListener('mouseup', handleDragEnd);
        isDragging = false;
    }

    // Load image to get its natural dimensions
    function loadImageForPreview(url, isInitialModalOpen = false) {
        if (!url) {
            naturalImageWidth = 0;
            naturalImageHeight = 0;
            currentImageScalePercentageWidth = 100.0;
            updatePreview();
            return;
        }

        const img = new Image();
        img.onload = function () {
            naturalImageWidth = this.width;
            naturalImageHeight = this.height;

            if (isInitialModalOpen) {
                // Initial background-size for the input field 
                let sizeForInput = bgSizeInput.value.trim().toLowerCase();
                // If .details had no background-size or it was 'auto', default to '100% auto'
                if (sizeForInput === 'cover' ||sizeForInput === '' || sizeForInput === 'auto' || sizeForInput === 'auto auto') {
                    bgSizeInput.value = '100% auto';
                }
                

                // Initial background-position for the input field
                let posForInput = bgPositionInput.value.trim().toLowerCase();
                if (posForInput === '' || posForInput === '0% 0%' || posForInput === 'left top' || posForInput === 'top left') {
                    bgPositionInput.value = '0px 0px'; // A common, clear default
                }
                
            }
            updatePreview(); // Update preview with potentially modified input values
        };
        img.onerror = function () {
            console.error("Error loading image for preview dimensions:", url);
            naturalImageWidth = 0;
            naturalImageHeight = 0;
            updatePreview();
        };
        img.src = url;
    }


    function updatePreview() {
        const imageUrl = imageUrlInput.value.trim();
        let bgPos = bgPositionInput.value.trim(); // Use value directly from input
        let bgSize = bgSizeInput.value.trim(); // Use value directly from input
        //const showEditedPreview = previewEditsToggle.checked;
        const showEditedPreview = true;


        previewBackgroundLayer.style.backgroundImage = 'none';
        previewForegroundLayer.style.backgroundImage = 'none';
        imagePreviewBox.classList.toggle('draggable', showEditedPreview && !!imageUrl);

        if (!imageUrl) {
            imagePreviewBox.style.backgroundColor = '#e0e0e0';
            return;
        }
        imagePreviewBox.style.backgroundColor = 'transparent';

        // Set defaults for style application if inputs are empty,
        // though loadImageForPreview should have set good defaults.
        const effectiveBgPos = bgPos || '0px 0px';
        const effectiveBgSize = bgSize || 'auto';

        if (showEditedPreview) {
            previewBackgroundLayer.style.backgroundImage = `url('${imageUrl}')`;
            previewBackgroundLayer.style.backgroundPosition = 'center center';
            previewBackgroundLayer.style.backgroundSize = 'contain';
            previewBackgroundLayer.style.opacity = '0.35';
            previewBackgroundLayer.style.display = 'block';

            previewForegroundLayer.style.backgroundImage = `url('${imageUrl}')`;
            previewForegroundLayer.style.backgroundPosition = effectiveBgPos;
            previewForegroundLayer.style.backgroundSize = effectiveBgSize;
            previewForegroundLayer.style.opacity = '1';
            previewForegroundLayer.style.display = 'block';
        } else { // Full Image Preview Mode
            previewBackgroundLayer.style.backgroundImage = `url('${imageUrl}')`;
            previewBackgroundLayer.style.backgroundPosition = 'center center';
            previewBackgroundLayer.style.backgroundSize = 'contain'; // 'contain' is key for full view
            previewBackgroundLayer.style.opacity = '1';
            previewBackgroundLayer.style.display = 'block';
            previewForegroundLayer.style.display = 'none';
        }
    }

    // --- Drag Logic ---
    previewForegroundLayer.addEventListener('mousedown', function (event) {
        //if (!previewEditsToggle.checked || !imageUrlInput.value.trim()) return;
        if (!imageUrlInput.value.trim()) return;

        event.preventDefault(); // Prevent text selection, etc.
        isDragging = true;
        imagePreviewBox.classList.add('dragging');

        const computedStyle = window.getComputedStyle(previewForegroundLayer);
        const currentPosition = computedStyle.backgroundPosition.split(' ');
        initialBgPosX = parseFloat(currentPosition[0]) || 0;
        initialBgPosY = parseFloat(currentPosition[1]) || 0;

        dragStartX = event.clientX;
        dragStartY = event.clientY;

        document.addEventListener('mousemove', handleDragMove);
        document.addEventListener('mouseup', handleDragEnd);
        document.addEventListener('mouseleave', handleDragEndOnLeave);
    });

    function handleDragMove(event) {
        if (!isDragging) return;
        const deltaX = event.clientX - dragStartX;
        const deltaY = event.clientY - dragStartY;

        const newBgPosX = initialBgPosX + deltaX;
        const newBgPosY = initialBgPosY + deltaY;

        const newPosString = `${newBgPosX.toFixed(0)}px ${newBgPosY.toFixed(0)}px`;
        previewForegroundLayer.style.backgroundPosition = newPosString;
        bgPositionInput.value = newPosString;
        // No need to call full updatePreview here, direct manipulation is faster during drag
    }

    function handleDragEnd() {
        if (!isDragging) return;
        isDragging = false;
        imagePreviewBox.classList.remove('dragging');
        document.removeEventListener('mousemove', handleDragMove);
        document.removeEventListener('mouseup', handleDragEnd);
        document.addEventListener('mouseleave', handleDragEndOnLeave);
        // Optional: call updatePreview() if other state needs to be synced after drag
    }

    function handleDragEndOnLeave(event) { // If mouse leaves the window
        if (event.relatedTarget === null && isDragging) { // relatedTarget is null when leaving window
            handleDragEnd();
        }
    }

    // --- Zoom Logic ---
    function handleZoom(direction) {

        let sizeVal = bgSizeInput.value.trim().toLowerCase();
        let matchPercent = sizeVal.match(/^(\d+)%/);
        let currentPercent = 100;

        if (sizeVal === 'cover' || sizeVal === 'contain' || sizeVal === '' || sizeVal === 'auto' || sizeVal === 'auto auto') {
            currentPercent = 100;
        } else if (matchPercent) {
            currentPercent = parseFloat(matchPercent[1]);
        } else {
            //  fallback to 100
            const computedSize = window.getComputedStyle(previewForegroundLayer).backgroundSize;
            let m = computedSize.match(/^(\d+)%/);
            if (m) currentPercent = parseFloat(m[1]);
            else currentPercent = 100;
        }

        // Zoom by 10% each click
        const step = 10;
        if (direction === 'in') currentPercent += step;
        if (direction === 'out') currentPercent = Math.max(10, currentPercent - step);

        // Compose new background-size value (preserve aspect: width% auto)
        const newSize = `${currentPercent}% auto`;

        
        previewForegroundLayer.style.backgroundSize = newSize;
        bgSizeInput.value = newSize; 
    }

    zoomInBtn.addEventListener('click', () => handleZoom('in'));
    zoomOutBtn.addEventListener('click', () => handleZoom('out'));

    // --- Event Listeners & Save ---
    modalCloseButton.addEventListener('click', closeModal);
    cancelBannerChangesButton.addEventListener('click', closeModal);
    window.addEventListener('click', function (event) {
        if (event.target == modal) closeModal();
    });

    // Copy Definition to clipboard
    copyBannerCssBtn.addEventListener('click', function () {
        if (!currentEditingDetailsDiv) return;

        // 1. Get the title (inside class="title" in .details)
        const titleSpan = currentEditingDetailsDiv.querySelector('.title');
        const title = titleSpan ? titleSpan.innerText.trim() : '[No title]';

        // 2. Get current styles
        const imageUrl = imageUrlInput.value.trim();
        const bgPos = bgPositionInput.value.trim();
        const bgSize = bgSizeInput.value.trim();

        // Compose the CSS string
        let cssString = `background-image: url("${imageUrl}"); background-position: ${bgPos}; background-size: ${bgSize};`;

        // Compose the final clipboard string
        const clipboardText = `${title}  "${cssString}"`;

        // Copy to clipboard using Clipboard API
        navigator.clipboard.writeText(clipboardText).then(() => {
            copyBannerCssBtn.textContent = "Copied!";
            setTimeout(() => copyBannerCssBtn.textContent = "Copy CSS", 1200);
        }, () => {
            copyBannerCssBtn.textContent = "Copy Failed";
            setTimeout(() => copyBannerCssBtn.textContent = "Copy CSS", 1200);
        });
    });

    imageUrlInput.addEventListener('change', function () {
        loadImageForPreview(this.value.trim(), false); // false: not the initial modal open, respect user inputs more
    });
    // These inputs will call updatePreview, which now directly uses their values
    bgPositionInput.addEventListener('input', updatePreview);
    bgSizeInput.addEventListener('input', updatePreview);
    //previewEditsToggle.addEventListener('change', updatePreview);

    saveBannerChangesButton.addEventListener('click', function () {
        if (currentEditingDetailsDiv) {
            const newImageUrl = imageUrlInput.value.trim();
            let newBgPosition = bgPositionInput.value.trim();
            let newBgSize = bgSizeInput.value.trim();

            if (newImageUrl) currentEditingDetailsDiv.style.backgroundImage = `url('${newImageUrl}')`;
            else currentEditingDetailsDiv.style.backgroundImage = 'none';

            currentEditingDetailsDiv.style.backgroundPosition = newBgPosition;
            currentEditingDetailsDiv.style.backgroundSize = newBgSize;
            closeModal();
        }
    });

    const editButtons = document.querySelectorAll('.edit-banner-button');
    editButtons.forEach(button => {
        button.addEventListener('click', function (event) {
            event.stopPropagation(); event.preventDefault();
            const detailsDiv = this.closest('.details');
            if (detailsDiv) openModal(detailsDiv);
        });
    });
});