/**
 * Card hover preview functionality with dynamic positioning
 *
 * This script creates a fixed-position tooltip that appears in the main window
 * even when hovering over cards in the sidebar, preventing clipping issues.
 */

(function() {
    'use strict';

    // Create a single tooltip element that will be reused
    let tooltip = null;

    function getTooltipSize() {
        // Responsive sizing based on viewport width
        if (window.innerWidth <= 480) {
            return { width: 140, height: 196 };
        } else if (window.innerWidth <= 768) {
            return { width: 175, height: 245 };
        } else {
            return { width: 250, height: 350 };
        }
    }

    function createTooltip() {
        if (tooltip) return tooltip;

        const size = getTooltipSize();
        tooltip = document.createElement('div');
        tooltip.id = 'card-hover-tooltip';
        tooltip.style.cssText = `
            position: fixed;
            width: ${size.width}px;
            height: ${size.height}px;
            background-color: #0d0d0d;
            background-size: contain;
            background-repeat: no-repeat;
            background-position: center;
            border: 2px solid #333;
            border-radius: 12px;
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.8);
            z-index: 99999;
            opacity: 0;
            visibility: hidden;
            pointer-events: none;
            transition: opacity 0.2s ease-in-out, visibility 0.2s ease-in-out;
        `;
        document.body.appendChild(tooltip);
        return tooltip;
    }

    function positionTooltip(cardElement, imageUrl, useLeftSide) {
        const tooltip = createTooltip();
        const rect = cardElement.getBoundingClientRect();
        const size = getTooltipSize();

        // Set the background image
        tooltip.style.backgroundImage = `url('${imageUrl}')`;

        // Update tooltip size in case window was resized
        tooltip.style.width = `${size.width}px`;
        tooltip.style.height = `${size.height}px`;

        // Calculate position
        let left, top;
        const margin = window.innerWidth <= 480 ? 8 : 12;

        if (useLeftSide) {
            // Position to the left of the card
            left = rect.left - size.width - margin;
            // Ensure it doesn't go off the left edge
            if (left < margin) {
                left = margin;
            }
        } else {
            // Position to the right of the card
            left = rect.right + margin;
            // Ensure it doesn't go off the right edge
            if (left + size.width > window.innerWidth) {
                left = rect.left - size.width - margin;
            }
        }

        // Center vertically relative to the card
        top = rect.top + (rect.height / 2) - (size.height / 2);

        // Ensure it doesn't go off the top or bottom
        if (top < margin) {
            top = margin;
        } else if (top + size.height > window.innerHeight) {
            top = window.innerHeight - size.height - margin;
        }

        tooltip.style.left = `${left}px`;
        tooltip.style.top = `${top}px`;
        tooltip.style.opacity = '1';
        tooltip.style.visibility = 'visible';
    }

    function hideTooltip() {
        if (tooltip) {
            tooltip.style.opacity = '0';
            tooltip.style.visibility = 'hidden';
        }
    }

    function attachHoverListeners() {
        // Find all card hover elements
        const cardHovers = document.querySelectorAll('.card-hover');
        console.log('Card hover script loaded - found', cardHovers.length, 'card elements');

        cardHovers.forEach(card => {
            // Skip if already has listeners
            if (card.dataset.hoverAttached) return;
            card.dataset.hoverAttached = 'true';

            // Get the image URL from the CSS variable
            const imageUrl = card.style.getPropertyValue('--card-image-url');
            if (!imageUrl) {
                console.log('No image URL found for card:', card.textContent);
                return;
            }

            // Extract actual URL from url('...')
            const urlMatch = imageUrl.match(/url\(['"]?([^'"]+)['"]?\)/);
            const actualUrl = urlMatch ? urlMatch[1] : null;
            if (!actualUrl) {
                console.log('Could not parse URL from:', imageUrl);
                return;
            }

            console.log('Attaching hover to card:', card.textContent, 'URL:', actualUrl);

            // Check if this is in the sidebar (left-hover class)
            const useLeftSide = card.classList.contains('hover-left');

            // Mouse hover events
            card.addEventListener('mouseenter', function() {
                console.log('Mouse entered card:', this.textContent);
                positionTooltip(this, actualUrl, useLeftSide);
            });

            card.addEventListener('mouseleave', function() {
                hideTooltip();
            });

            // Keyboard focus events (accessibility)
            card.addEventListener('focusin', function() {
                positionTooltip(this, actualUrl, useLeftSide);
            });

            card.addEventListener('focusout', function() {
                hideTooltip();
            });

            // Also hide on scroll
            window.addEventListener('scroll', hideTooltip, { passive: true });
        });
    }

    // Run on page load
    console.log('Card hover script initializing, document state:', document.readyState);

    function init() {
        console.log('Running initial attachment');
        attachHoverListeners();

        // Also try again after a short delay for dynamically loaded content
        setTimeout(attachHoverListeners, 1000);
        setTimeout(attachHoverListeners, 2000);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    // Re-run when new content is added (for dynamic updates)
    const observer = new MutationObserver(function(mutations) {
        // Debounce to avoid excessive re-attachment
        clearTimeout(observer.timeout);
        observer.timeout = setTimeout(attachHoverListeners, 100);
    });

    // Wait for body to exist before observing
    if (document.body) {
        observer.observe(document.body, {
            childList: true,
            subtree: true
        });
    } else {
        document.addEventListener('DOMContentLoaded', function() {
            observer.observe(document.body, {
                childList: true,
                subtree: true
            });
        });
    }
})();
