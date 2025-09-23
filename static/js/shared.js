/* Vote For Me - Shared JavaScript Functions */

// Mobile navigation toggle
function toggleMobileNav() {
    const navLinks = document.getElementById('nav-links');
    const navToggle = document.querySelector('.nav-toggle i');
    
    navLinks.classList.toggle('nav-open');
    
    if (navLinks.classList.contains('nav-open')) {
        navToggle.className = 'fas fa-times';
    } else {
        navToggle.className = 'fas fa-bars';
    }
}

// Close mobile nav when clicking outside
function setupMobileNavClose() {
    document.addEventListener('click', function(e) {
        const navPane = document.querySelector('.nav-pane');
        const navLinks = document.getElementById('nav-links');
        
        if (!navPane.contains(e.target) && navLinks.classList.contains('nav-open')) {
            navLinks.classList.remove('nav-open');
            const navToggle = document.querySelector('.nav-toggle i');
            if (navToggle) {
                navToggle.className = 'fas fa-bars';
            }
        }
    });
}

// Navigation hide-on-scroll functionality
function setupNavHideOnScroll() {
    let lastScrollTop = 0;
    let scrollTimeout;
    const navigation = document.getElementById('navigation');
    
    if (!navigation) return; // Exit if no navigation element
    
    function handleNavVisibility() {
        clearTimeout(scrollTimeout);
        scrollTimeout = setTimeout(function() {
            const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
            
            if (scrollTop > lastScrollTop && scrollTop > 80) {
                // Scrolling down & past threshold
                navigation.classList.add('nav-hidden');
            } else {
                // Scrolling up
                navigation.classList.remove('nav-hidden');
            }
            lastScrollTop = scrollTop <= 0 ? 0 : scrollTop;
        }, 10);
    }
    
    // Add scroll listener
    window.addEventListener('scroll', handleNavVisibility, { passive: true });
    
    // Show navigation on mouse move near top
    document.addEventListener('mousemove', function(e) {
        if (e.clientY <= 100) {
            navigation.classList.remove('nav-hidden');
        }
    });
}

// Initialize shared functionality when DOM is loaded
function initializeSharedComponents() {
    setupMobileNavClose();
    setupNavHideOnScroll();
}

// Auto-initialize when included
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeSharedComponents);
} else {
    initializeSharedComponents();
}
