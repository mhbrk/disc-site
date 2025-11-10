landing_page_instructions = """
# Landing Page Template

## Questions to ask
- **You will only ask these exact questions, and no other questions**
1. Ask to provide a business plan or a detailed description of business idea.
2. Ask about Design system in non-technical terms and may not be familiar website design (ask a couple questions and then come up with the design system)

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


## Follow up Questions
**This section is not supposed to be a part of the final specification. These are instructions for how let user fill in missing information. As information is filled in, you will remove the buttons form the spec.**

### Overview
Once you are done with the template instructions, you will have produce a clear and concise website specification.
However, in order to avoid asking too many questions at the same time, the spec will contain AI generated text and assumptions.
To make the website production ready, we will need to address all the assumptions and replace made up content with actual information.
To address this, we will place red circular buttons throughout the page that will initiate a conversation with the user to fill in missing information.

### Implementation
The buttons will be small red circular buttons without text or icon and will be placed in the area where more user information is needed.
The buttons will be on top of existing content, they should not affect layout.
For sections not visible to the user such as head element, just put the red buttons at the top of the page.

The buttons will execute the following javascript:
window.parent.postMessage({ action: "sendToChat", message: "Some message here"});

The message field will be from the user perspective and will initiate a conversation about filling in missing information required to make the site ready for production.
Here are some example questions, but you could have more or fewer depending on the user provided information and the spec:
1) Please guide me through the process of finalizing SEO. You must ask questions, there should be no assumptions, or fake details.
2) Please guide me through setting up social media links. You must ask questions, there should be no assumptions, or fake details.
3) Please guide me through finalizing my form. You must ask questions, there should be no assumptions, or fake details.
4) etc.
"""

