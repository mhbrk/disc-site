// Mobile Navigation Toggle
document.addEventListener('DOMContentLoaded', function () {
    const navMenu = document.querySelector('.nav-menu');
    const navActions = document.querySelector('.nav-actions');


    // Close mobile menu when clicking on a link
    const navLinks = document.querySelectorAll('.nav-link');
    navLinks.forEach(link => {
        link.addEventListener('click', () => {
            navMenu.classList.remove('active');
            navActions.classList.remove('active');
        });
    });

    // FAQ Accordion
    const faqQuestions = document.querySelectorAll('.faq-question');
    faqQuestions.forEach(question => {
        question.addEventListener('click', () => {
            const faqItem = question.parentElement;
            const answer = faqItem.querySelector('.faq-answer');
            const icon = question.querySelector('i');

            // Close other FAQ items
            faqQuestions.forEach(otherQuestion => {
                if (otherQuestion !== question) {
                    const otherItem = otherQuestion.parentElement;
                    const otherAnswer = otherItem.querySelector('.faq-answer');
                    const otherIcon = otherQuestion.querySelector('i');

                    otherAnswer.style.maxHeight = null;
                    otherIcon.style.transform = 'rotate(0deg)';
                    otherItem.classList.remove('active');
                }
            });

            // Toggle current FAQ item
            if (faqItem.classList.contains('active')) {
                answer.style.maxHeight = null;
                icon.style.transform = 'rotate(0deg)';
                faqItem.classList.remove('active');
            } else {
                answer.style.maxHeight = answer.scrollHeight + 'px';
                icon.style.transform = 'rotate(180deg)';
                faqItem.classList.add('active');
            }
        });
    });

    // Smooth scrolling for navigation links
    const navLinksSmooth = document.querySelectorAll('a[href^="#"]');
    navLinksSmooth.forEach(link => {
        link.addEventListener('click', function (e) {
            e.preventDefault();
            const targetId = this.getAttribute('href');
            const targetSection = document.querySelector(targetId);

            if (targetSection) {
                const offsetTop = targetSection.offsetTop - 80; // Account for fixed navbar
                window.scrollTo({
                    top: offsetTop,
                    behavior: 'smooth'
                });
            }
        });
    });

    // Copy URL functionality
    const copyButtons = document.querySelectorAll('.btn-secondary');
    copyButtons.forEach(button => {
        if (button.textContent.includes('Copy')) {
            button.addEventListener('click', function () {
                const urlText = this.previousElementSibling.textContent;
                navigator.clipboard.writeText(urlText).then(() => {
                    const originalText = this.textContent;
                    this.textContent = 'Copied!';
                    this.style.background = '#10b981';
                    this.style.color = 'white';

                    setTimeout(() => {
                        this.textContent = originalText;
                        this.style.background = '';
                        this.style.color = '';
                    }, 2000);
                });
            });
        }
    });

    // Animate elements on scroll
    const observerOptions = {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    };

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('animate-in');
            }
        });
    }, observerOptions);

    // Observe elements for animation
    const animateElements = document.querySelectorAll('.feature-card, .testimonial-card, .pricing-card');
    animateElements.forEach(el => {
        observer.observe(el);
    });

    // Parallax effect for hero section
    window.addEventListener('scroll', () => {
        const scrolled = window.pageYOffset;
        const hero = document.querySelector('.hero');
        const floatingCard = document.querySelector('.floating-card');

        if (hero && floatingCard) {
            const rate = scrolled * -0.5;
            floatingCard.style.transform = `translateY(${rate}px)`;
        }
    });

    // Add loading animation
    window.addEventListener('load', () => {
        document.body.classList.add('loaded');
    });
});

// Add some interactive hover effects
document.addEventListener('DOMContentLoaded', function () {
    // Add hover effects to cards
    const cards = document.querySelectorAll('.feature-card, .testimonial-card, .pricing-card');
    cards.forEach(card => {
        card.addEventListener('mouseenter', function () {
            this.style.transform = 'translateY(-10px) scale(1.02)';
        });

        card.addEventListener('mouseleave', function () {
            this.style.transform = 'translateY(0) scale(1)';
        });
    });

    // typing effect (target the overlay span, not the H1)
    const typingEl = document.getElementById('heroTyping');
    const ghostEl = document.getElementById('heroGhost');

    if (typingEl && ghostEl) {
        const text = ghostEl.textContent.trim(); // plain text for typing
        typingEl.textContent = '';
        typingEl.style.borderRight = '2px solid rgba(255,255,255,.9)';

        let i = 0;
        const step = () => {
            if (i < text.length) {
                typingEl.textContent += text.charAt(i++);
                setTimeout(step, 50);
            } else {
                typingEl.style.borderRight = 'none';
                // swap to the final HTML so your gradient span appears
                typingEl.innerHTML = ghostEl.innerHTML;
            }
        };
        setTimeout(step, 500);
    }
});


// Waitlist Modal logic
function openWaitlistModal() {
    var waitlistModal = new bootstrap.Modal(document.getElementById('waitlistModal'));
    waitlistModal.show();
}

document.querySelectorAll('.join-waitlist-btn').forEach(btn => {
    btn.addEventListener('click', openWaitlistModal);
});
// Optional: Close modal on ESC
document.addEventListener('keydown', function (e) {
    if (e.key === "Escape") {
        var modalEl = document.getElementById('waitlistModal');
        if (modalEl && modalEl.classList.contains('show')) {
            bootstrap.Modal.getInstance(modalEl).hide();
        }
    }
});


document.getElementById("brebaWaitlistForm").addEventListener("submit", async function (e) {
    e.preventDefault();

    const form = e.target;
    const data = {
        email: form.email.value,
        alphaAccess: form.alphaAccess?.value || "",
        privateCloud: form.privateCloud?.value || "",
        comments: form.comments.value
    };

    const alertBox = document.getElementById("formAlert");
    const submitBtn = document.getElementById("submitBtn");
    const spinner = document.getElementById("submitSpinner");
    const submitText = document.getElementById("submitText");

    alertBox.classList.add("d-none");
    spinner.classList.remove("d-none");
    submitText.textContent = "Submitting...";

    try {
        const response = await fetch("https://script.google.com/macros/s/AKfycbwCbKjWjO4ZkDWzFCeh7zo7e1rnHu6OP-ydwlJVJRyp-AjGav1gaG_5N1yEzOArvklW/exec", {
            method: "POST",
            mode: "no-cors",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify(data)
        });

        form.reset();
        alertBox.className = "alert alert-success";
        alertBox.textContent = "🎉 Thank you! Your response has been recorded.";
        alertBox.classList.remove("d-none");

        // Wait 1.5s then close modal
        setTimeout(() => {
            const modal = bootstrap.Modal.getInstance(document.getElementById("waitlistModal"));
            modal.hide();
            alertBox.classList.add("d-none"); // hide alert after closing
        }, 1000);

    } catch (error) {
        alertBox.className = "alert alert-danger";
        alertBox.textContent = "❌ There was an error submitting the form. Please try again.";
        alertBox.classList.remove("d-none");
        console.error("Submission failed", error);
    }

    spinner.classList.add("d-none");
    submitText.textContent = "Submit";
});


document.getElementById("buildAppBtn").addEventListener("click", function () {
    const idea = document.getElementById("buildAppInput").value; // get input value
    const textarea = document.getElementById("comments");
    textarea.value = idea; // put into textarea
});

document.getElementById('waitlistModal').addEventListener('shown.bs.modal', function () {
    const emailInput = document.querySelector('#waitlistModal input[name="email"]');
    if (emailInput) {
        emailInput.focus();
    }
});


const modal = document.getElementById('demoModal');
const frame = document.getElementById('demoVideo');

// When the trigger is clicked, set the iframe src (with autoplay)
document.querySelectorAll('[data-bs-target="#demoModal"]').forEach(el => {
    el.addEventListener('click', function () {
        const url = this.getAttribute('data-video')
            || 'https://www.youtube.com/embed/Txv-lUdk1LM?rel=0&autoplay=1&rel=0';
        frame.src = url;
    });
});

// When modal closes, stop the video by clearing src
modal.addEventListener('hidden.bs.modal', function () {
    frame.src = '';
});
