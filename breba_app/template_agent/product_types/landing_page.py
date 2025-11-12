follow_up_instructions = """
## Follow up Questions
In order to avoid asking too many questions at the same time, the spec will contain AI generated text and assumptions.
To make the website production ready, we will need to address all the assumptions and replace made up content with actual information.
Follow up question buttons are red round buttons without text or icon and will be spaced across the top over the navbar. 
The button click will send the questions to chat using: window.parent.postMessage({ action: "sendToChat", message: question });
The question is from the user's perspective and is a shortcut to start a conversation about making sure the information is correct.
The Follow up Buttons MUST NOT impact layout. They should be on top of the content.

### Follow up Questions
**Use these exact phrases**
1) SEO tags may contain AI generated content. Ask questions to make sure the website has correct SEO tags.
2) Let's fix the social media icons in the footer. Ask questions to make sure social media in the footer are correct.
3) Ask questions to make sure form API_Key and other information is not AI Generated?  # Use the actual name of the form/button for the actual user website
"""

landing_page_instructions = f"""
# Instructions for building a Landing Page

## Questions to ask
- **You will only ask these exact questions, and no other questions**
1. Ask to provide a business plan or a detailed description of business idea.
2. Ask about Design system in non-technical terms and may not be familiar website design (ask a couple questions and then come up with the design system)

{follow_up_instructions}

## Design System
- You will come up with a color palette, typography, spacing, and other design elements.(Do not ask direct questions about this, just make up whatever you think makes sense given answers to your questions)

## Layout
- You will have a navbar that scrolls to different section of the page.
  - The navbar will have a logo and a call to action button 
- At the top the hero section with a call to action button and a catchy slogan.
- Then Benefits section with 3 benefits
- Then How It Works section with 3 steps
- Then Testimonials section with 3 testimonials
- Then Pricing section with 3 pricing plans
- FAQs section with 5 questions based on the business plan
- Footer with social media icons
- Modal form with fields: Name, Email, Company, Message
  - the form will use staticforms.xyz with ajax for submission.
  - The form will have hidden fields for: subject, replyTo, apiKey.

## SEO
- You must fill out all SEO tags.

## Technical requirements
- The page should be responsive.
- The page should be mobile-first.
- The page should be accessible.
- The page should be optimized for speed.
- The page should be optimized for security.
- The page should be optimized for SEO.
- The page should support Google Analytics.
- Do not use inline styles.

## Defaults (Use this unless user specifies other preferences)
- Use Google icons or other publicly available images when appropriate
- Use https://cdn.breba.app/templates/images/logo.png as the logo in the navbar and anywhere else a logo appears.
- Use https://cdn.breba.app/templates/images/hero.jpg as the hero image in the Hero section.
- Use Bootstrap 5.3.8 via CDN for core styling (without integrity check):
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.8/dist/css/bootstrap.min.css" rel="stylesheet">
  <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
"""

landing_page_coder_instructions = follow_up_instructions + """

Follow up button style to be put in the head styles tag:
```css
/* --- Circular red button --- */
.follow-up-btn {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  border: none;
  background-color: #ff3b30;
  box-shadow: 0 0 6px rgba(0,0,0,0.25);
  cursor: pointer;
  position: absolute;
  right: 8px;
  transition: transform 0.15s ease,
              background-color 0.2s ease,
              box-shadow 0.2s ease;
}

.follow-up-btn:hover {
  background-color: #d93025;
  transform: scale(1.2);
  box-shadow: 0 0 8px rgba(0,0,0,0.35);
}
```

Script for adding before the closing body tag
```javascript
document.querySelectorAll("[data-follow-up-question]").forEach((btn) => {
  const question = btn.getAttribute("data-follow-up-question");
  btn.addEventListener("click", (event) => {
    event.stopPropagation(); // if needed
    window.parent.postMessage({ action: "sendToChat", message: question });
  });
});
```

Use this HTML for the buttons directly on the body tag:
```html
<button class="follow-up-btn" style="top: 10px; left: 50%;" 
  title="Finalize SEO"
  data-follow-up-question="SEO tags may contain AI generated content. Ask all necessary questions to make sure the website has correct SEO tags.">
</button>

<button class="follow-up-btn" style="top: 10px; left: calc(50% + 40px);" 
  title="Finalize Social Media"
  data-follow-up-question="Let's fix the social media icons in the footer. Ask all necessary questions to make sure social media in the footer are correct.">
</button>

<!-- Use the actual name of the form/button for the actual user website -->
<button class="follow-up-btn" style="top: 10px; left: calc(50% + 80px);" 
  title="Finalize Form Setup"
  data-follow-up-question="Ask all necessary questions to make sure form API_Key and other form information is not AI Generated?">
</button>
```
"""

