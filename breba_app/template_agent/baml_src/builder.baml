class Question {
  question string @description("Question that requires the user to answer")
}

class WebsiteSpecification {
  spec string @description("Full website specification")
}

class LLMMessage {
  role "user" | "assistant"
  content string
}

template_string  SystemInfo() #"
    The website will be static, but when generating it, 
    the generator will be able to use tools to fetch dynamic content before generating the static html.  
    For this project all the things will go into a single index.html.
"#

template_string TemplatingInstructions() #"
Your job is to follow instructions in the template and generate a good website specification.

**You will ask questions** 
Ask one question at a time and wait for the answer before asking the next question. 
Questions should be very simple and easy to answer with one word or a short phrase.
"#

template_string GoodWebsiteSpecification() #"
**Generating good website specifications** 
Your final website specification will be sent to another agent to generate HTML. 
The html generating agent has access to tools like web search and image generation to help generate the HTML.

You need to be very detailed to make sure that the prompt can be used to generate a fully working HTML site. 

IMPORTANT: The website specification must be atomic and should be **self-contained** without referencing any parts of the conversation with the user. 

The HTML generator will use only the final website specification to construct the site.
All the information the user provides must be worked into the website specification so that the HTML generator can generate the website consistently and to the user's needs.
After getting answers to your questions, you will always respond with the complete website specification.  

You are producing a high quality PRD for the website and it needs to clear and concise. Avoid repeatig instructions and unnecessary section.

Here is an example of a website specification:

# 🎂 Birthday Website Specification

## 1. Overview

This is a static HTML website for a personal birthday celebration.
It will be shared with friends and should present all key event information clearly, with an embedded Google Form for RSVP.

The site must be:
- Elegant and modern-minimal in visual style
- Mobile-friendly and easy to navigate
- Deliverable as a single static site self-contained in a single index.html file (HTML, CSS, JS)

---

## 2. Design System

- **Design Aesthetic**: Classy, modern-minimal
- **Typography**: Clean sans-serif for body text; consider elegant serif for headings
- **Colors**: Neutral or refined palette (e.g., white, black, light beige, subtle gold/gray accents)
- **Layout**:
  - One-page scroll or simple vertical section structure
  - No unnecessary animations or visual noise
  - Prioritize clarity and visual balance
- **Theme**:
  - Light theme

---

## 3. Content to Include

### Hero Section

- **Greeting / Title**:
  _"You're invited to Yason’s birthday!"_

- **Photo**:
  Display image from:
  `https://cdn.breba.app/abc/123/my_photo.png`

---

### Event Details

Display clearly and accessibly:
- **Date**: July 7, 2025
- **Time**: 7:00 PM
- **Location**: 123 ABC St, Seattle, WA
- **Dress Code**: Black and White

---

### RSVP Section

- Embed the following Google Form directly into the page:
  `https://forms.gle/gtPhM82xcEXF9YaKA`

**Requirements**:
- Responsively sized iframe
- Introduced with heading like _“Let me know if you’re coming!”_
- Match the form styling (if possible) to the rest of the site

---

### Available assets
https://cdn.breba.app/images/logo_light.png - Use this for logo image for the light theme
https://cdn.breba.app/images/avatar.png - Use this for my avatar
"#


function GenerateSpecificationFromTemplate(messages: LLMMessage[]) -> Question | WebsiteSpecification {
  client CustomGPT5
  prompt #"
    You are an AI agent. You are helping a user to craft a website specification (PRD). 

    {{ ctx.output_format }}

    {{ SystemInfo() }}

    {{ TemplatingInstructions() }}

    {{ GoodWebsiteSpecification() }}    

    {% for message in messages %}
      {{ _.role(message.role) }} 
      {{ message.content }}
    {% endfor %}

    {{ _.role("system") }}
    {{ ctx.output_format }}

  "#
}

test SimpleQuestion {
  functions [GenerateSpecificationFromTemplate]
  args {
    messages [
      {
        role "user"
        content #"
# Instructions for building a Landing Page

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
  <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script># Landing Page Template

"#
      }
      {
        role "assistant"
        content "Please provide a brief business plan or a detailed description of your business idea."
      }
      {
        role "user"
        content "We are changing the way people treat documents. We are proposing that everything is a document or deserves a document. You morning routine is a document, your vacation plan is a document. And we will have AI agents who help you organize documents and present you the relevant info and documents when you need it."
      }
      {
        role "assistant"
        content "What overall vibe should the site convey (e.g., futuristic, friendly, professional, playful) and do you prefer light or dark theme?"
      }
      {
        role "user"
        content "Brutalist."
      }
    ]
  }
}