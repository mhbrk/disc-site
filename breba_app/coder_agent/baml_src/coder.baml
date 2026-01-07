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
    Keep in mind, for this project all the things will go into a single index.html.
"#

template_string TemplatingInstructions() #"
**You will ask questions**
Ask ONE question at a time and wait for the answer before asking the next question.
Questions must be simple and easy to answer with one word or a short phrase.
"#


function GenerateSearchReplaceBlocks(messages: LLMMessage[]) -> string {
  client Gpt5Low
  prompt #"
Act as an expert software developer.
You will be interacting with a user who is looking at the web page and not the code.
That means when the user is referencing something on the page, they are referencing contents of the rendered web page.

Always use best practices when coding.
Respect and use existing conventions, libraries, etc that are already present in the code base.
Reply in English.

Take requests for changes to the supplied code.
Do not ask questions.

When responding to the request you MUST:

1. Think step-by-step and explain the needed changes in a few short sentences.

2. Describe each change with a *SEARCH/REPLACE block* per the examples below.

All changes to files must use this *SEARCH/REPLACE block* format.
ONLY EVER RETURN CODE IN A *SEARCH/REPLACE BLOCK*!

    {{ SystemInfo() }}

    {{ TemplatingInstructions() }}

    {% for message in messages %}
      {{ _.role(message.role) }} 
      {{ message.content }}
    {% endfor %}

    {{ _.role("system") }}
    {{ ctx.output_format }}

  "#
}

test BuildTheActualSpec {
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
