class Coder {
  coder_request string  @description("At most one short sentence for coder agent. Coder agent has the full conversation context so don't provide details. For example: 'Build the website' or 'Fix the bug' or 'Add the new section'")
}

class ResponseToUser {
  response string  @description("Response to user from chat agent")
}

template_string  ChatSystemInfo() #"<system_info>
    Keep in mind, this project is an html page that follows best practices.
    Breba app is producing a production ready website that geared towards search engine discoverabilty and core web vitals.
    The website is static in nature, but can use plugin for dynamic functionality.
</system_info>
"#

function UserResponseOrCoder(messages: LLMMessage[], spec: string, files: string[]) -> ResponseToUser | Coder {
  client Gpt5Low
  prompt #"
  You are an AI agent within Breba App. You will talk with user and when appropriate route them to the coder agent.
If the request is ambiguous, ask questions.
Ask one question at a time and wait for the answer before asking the next question. Questions should be very simple and easy to answer with one word or a short phrase.

You may also answer user questions about the current state of the website.

Once you understand the request you MUST either invoke Coder agent or resond to the user with a question or an answer.

IMPORTANT: You ARE NOT WRITING ANY CODE YOURSELF.
IMPORTANT: If something doesn't make sense, ask questions until it does.


{{ChatSystemInfo()}}

    {{ _.role("system") }}
    {{ ctx.output_format }}

  {% if spec %}
    {{ _.role("user") }}
    I have the following specification for the website:
  {{ spec }}

    {{ _.role("assistant") }}
    Ok. I understand the context of the website.
  {% endif %}

  {% if files %}
    {{ _.role("user") }}
    Here are the files that exist in the project:
    {{ files }}
    
    {{ _.role("assistant") }}
    Great this helps me understand the state of the project.
  {% endif %}


    {% for message in messages %}
      {{ _.role(message.role) }} 
      {{ message.content }}
    {% endfor %}



  "#
}

test BuildHelloWorldSite {
  functions [UserResponseOrCoder]
  args {
    messages [
      {
        role "user"
        content #"Build a hello world website for me."#
      }
    ],
    spec "This is a brand new project without a spec",
    files []

  }
  
}


test BuildHelloWorldSiteNoQuestions {
  functions [UserResponseOrCoder]
  args {
    messages [
      {
        role "user"
        content #"Build a hello world website for me. Do not ask questions"#
      }
    ],
    spec #"This is a brand new project without a spec"#,
    files []
  }
}

test BuildHelloWorldSiteMultiTurn {
  functions [UserResponseOrCoder]
  args {
    messages [
      {
        role "user"
        content #"Build a hello world website for me."#
      },
      {
        role "assistant"
        content #"What is the main purpose of your Hello World website (for example: personal profile, business landing page, or just a simple demo)?""#
      },
      {
        role "user"
        content #"This is a simple demo. It doesn't matter"#
      },
    ],
    spec #"This is a brand new project without a spec"#,
    files []
  }
}


test BuildLandingPage {
  functions [UserResponseOrCoder]
  args {
    messages [
      {
        role "user"
        content #"I would like to build a landing page for my startup."#
      },
      {
        role "assistant"
        content #"What is the name of your startup?"#
      },
      {
        role "user"
        content #"The name of my startup is TechNova."#
      },
      {
        role "assistant"
        content #"What is the main product or service offered by TechNova?"#
      },
      {
        role "user"
        content #"We offer innovative AI solutions for businesses."#
      },
    ],
    spec #""#,
    files []    
  }
}

test BuildLandingPageConfusion{
  functions [UserResponseOrCoder]
  args {
    messages [
      {
        role "user"
        content #"Rename Gravel Guard to Gravel Success."#
      },
      {
        role "assistant"
        content #"Got it, you want to rename the brand.\n\nShould we change **every occurrence** of “GravelGuard” to **“Gravel Success”** across the whole site (including title, headings, footer, schema, and form subject), or only the **visible text** on the page?"#
      },
      {
        role "user"
        content #"Everywhere. I'm rebranding"#
      },
    ],
    files ["index.html", "styles.css", "script.js", "sitemap.xml", "SPEC.md"]
    spec #"# GravelGuard — Product Specification

## 1. Product Intent

**GravelGuard** is a mobile gravel-road maintenance service focused on **small but critical access roads** (trailheads, rural properties, recreation access) that are underserved by traditional contractors.

The website’s sole job is to:

1. Clearly explain *what problem GravelGuard solves*
2. Establish *credibility and trust*
3. Convert visitors into *qualified inbound leads*

Primary conversion outcome:
**A visitor submits a request for a road assessment**

---

## 2. Target Users & Use Cases

### Primary User Segments

* Public land agencies and counties
* Rural property owners and HOAs
* Outdoor brands, clubs, and trail organizations

### Core Use Cases

* A land manager needs fast repair of a short gravel segment
* A property owner wants predictable access for guests
* An outdoor brand wants to sponsor and visibly support access roads

---

## 3. User Preferences (Non-negotiable)

* Content must feel **field-tested, professional, and practical**
* Tone must avoid:

  * Startup hype
  * “Tech platform” language
  * Playfulness or novelty
* Users prefer:

  * Clear scopes and timelines
  * Plain language explanations
  * Concrete examples (roads, trailheads, miles, days)

---

## 4. Core Invariants (Must Always Hold)

These are *product truths* that must not be violated by design or content changes:

1. **Clarity over cleverness**
   Users should understand the service in under 10 seconds.

2. **Lead capture is primary**
   Every major section must reinforce or support the primary CTA.

3. **Trust before pricing precision**
   Pricing is indicative, flexible, and contextual—not rigid or transactional.

4. **Small-segment specialization**
   GravelGuard is explicitly *not* a general road contractor.

5. **Fast response is a differentiator**
   Assessment and deployment speed is central to the value proposition.

---

## 5. Content Constraints

* Single narrative flow from:
  **Problem → Solution → Proof → Cost → Action**
* One primary call to action:
  **“Request a Road Assessment”**
* Secondary CTAs may exist, but must never compete with the primary CTA.
* All copy must support one of:

  * Understanding
  * Trust
  * Conversion

---

## 6. Information Architecture (Conceptual)

The page is a **single linear experience** composed of these conceptual sections:

1. **Value Proposition**

   * What GravelGuard does
   * Who it’s for
   * Why speed and focus matter

2. **Benefits**

   * Risk reduction (vehicles, guests)
   * Speed and flexibility
   * Fit for agencies and outdoor partners

3. **Process**

   * Simple, low-friction, three-step flow
   * Emphasis on minimal effort from the customer

4. **Social Proof**

   * Testimonials representing each major user segment
   * Realistic language, understated tone

5. **Pricing Orientation**

   * Example tiers to set expectations
   * Clear message: exact pricing requires assessment

6. **Objection Handling**

   * FAQs addressing scope, speed, eligibility, and pricing logic

---

## 7. Conversion Model

### Primary Action

* User submits a road assessment request containing:

  * Contact information
  * Road location
  * Description of issues

### Conversion Principles

* The form must feel:

  * Low effort
  * Non-binding
  * Consultative, not salesy
* Submission feedback must be immediate and reassuring.

---

## 8. Trust Signals (Required)

At least one of each must be present:

* **Operational credibility**

  * Equipment, crews, real-world constraints
* **Social proof**

  * Testimonials from agencies, owners, and sponsors
* **Professional restraint**

  * No exaggerated claims or guarantees beyond stated timelines

---

## 9. SEO & Discoverability (Conceptual)

The product must be clearly associated with:

* Gravel road repair
* Trailhead and recreation access
* Rural and remote access maintenance

SEO is supportive, not the primary UX driver:

* Content must read naturally to humans first.
* Keywords must reinforce meaning, not distort it.

---

## 10. Non-Goals (Explicit Exclusions)

The website is **not** intended to:

* Fully quote or book services
* Educate on road engineering theory
* Serve as a content blog or documentation hub
* Present GravelGuard as a generalized construction firm

---

## 11. Success Criteria

The specification is successful if:

* A first-time visitor understands the service quickly
* The service feels credible without over-explaining
* Users consistently choose to submit the assessment form
* The site attracts qualified, relevant inbound requests
"#
    
  }
}