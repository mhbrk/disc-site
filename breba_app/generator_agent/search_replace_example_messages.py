example_messages = [
    dict(
        role="user",
        content="I want to create another section for the Contact nav bar link",
    ),
    dict(
        role="assistant",
        content="""To make this change we need to modify `index.html` to:
1. Add the new section to the bottom of the page, above the footer.
2. Update navbar to add a new link to the new section.
Here are the *SEARCH/REPLACE* blocks:
index.html
```html
<<<<<<< SEARCH
            <a href="#about">About us</a>
=======
            <a href="#about">About us</a>
            <a href="#contact">Contact</a>
>>>>>>> REPLACE
```

index.html
```html
<<<<<<< SEARCH
    <!-- Footer Hero Section -->
    <section class="footer-hero">
        <img
            src="https://cdn.example.com/footer_hero.jpg"
            alt="Footer Hero – My Kids Club"
            loading="lazy"
        />
    </section>
    <!-- Footer -->
    <footer>
        &copy; 2025 My Kids Club. All rights reserved.
    </footer>
=======
<!-- Contact Section -->
    <section class="contact-section" id="contact">
        <h2>
            Contact Us
        </h2>
        <div>
            Have questions or want to book? Reach out to us!
        </div>
        <div>
            <div>
                <span >Email:</span>
                <a href="mailto:example@gmail.com" >mykidsclub@gmail.com</a>
            </div>
        </div>
    </section>
    <!-- Footer Hero Section -->
    <section class="footer-hero">
        <img
            src="https://cdn.breba.app/maya/457f209d-bcc5-41f7-803a-c1ba0880f949/footer_hero.jpg"
            alt="Footer Hero – My Kids Club"
            loading="lazy"
        />
        <div class="footer-hero-text" >
            We provide parents with peace of mind, helping them enjoy their ski trip by giving children exceptional care every fun-filled day in a place as nurturing as home.        </div>
    </section>
    <!-- Footer -->
    <footer>
        &copy; 2025 My Kids Club. All rights reserved.
    </footer>
>>>>>>> REPLACE
```
""",
    ),
    dict(
        role="user",
        content="""# Minimalistic "Hello World" Website Specification

## Overview

A static HTML website that displays the text "Hello World" centered both vertically and horizontally on a plain white background. The design is extremely minimalistic, with no additional elements, styles, or content.

## Visual Style

- **Background**: Solid white (#fff).
- **Text**: "Hello World" (no exclamation mark), using the browser’s default font, default size, and default color.
- **Layout**: The text is perfectly centered both vertically and horizontally in the viewport.
- **No navigation, footer, images, icons, or extra content.**
- **No external CSS or JavaScript.**

## Technical Implementation

- Use only standard HTML
- The text must be selectable.
- The site must be fully responsive"""
    ),
    dict(
        role="assistant",
        content="""Since `index.html` is empty I will provide entire html document:

Here are the *SEARCH/REPLACE* blocks:
index.html
```html
<<<<<<< SEARCH
=======
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Hello World</title>
  <meta name="viewport" content="width=device-width,initial-scale=1.0">
  <style>
    html, body {
      height: 100%;
      margin: 0;
      padding: 0;
      background: #fff;
      width: 100%;
    }
    body {
      min-height: 100vh;
      min-width: 100vw;
      height: 100vh;
      width: 100vw;
      display: flex;
      align-items: center;
      justify-content: center;
    }
  </style>
</head>
<body>
  Hello World
</body>
</html>
>>>>>>> REPLACE
```
""",
    ),
]
system_reminder = """# *SEARCH/REPLACE block* Rules:

Every *SEARCH/REPLACE block* must use this format:
1. The *FULL* file path alone on a line, verbatim. No bold asterisks, no quotes around it, no escaping of characters, etc.
2. The opening fence and code language, eg: ```python
3. The start of search block: <<<<<<< SEARCH
4. A contiguous chunk of lines to search for in the existing source code
5. The dividing line: =======
6. The lines to replace into the source code
7. The end of the replace block: >>>>>>> REPLACE
8. The closing fence: ```

Use the *FULL* file path, as shown to you by the user.

Every *SEARCH* section must *EXACTLY MATCH* the existing file content, character for character, including all comments, docstrings, etc.
If the file contains code or other data wrapped/escaped in json/xml/quotes or other containers, you need to propose edits to the literal contents of the file, including the container markup.

*SEARCH/REPLACE* blocks will *only* replace the first match occurrence.
Including multiple unique *SEARCH/REPLACE* blocks if needed.
Include enough lines in each SEARCH section to uniquely match each set of lines that need to change.

Keep *SEARCH/REPLACE* blocks concise.
Break large *SEARCH/REPLACE* blocks into a series of smaller blocks that each change a small portion of the file.
Include just the changing lines, and a few surrounding lines if needed for uniqueness.
Do not include long runs of unchanging lines in *SEARCH/REPLACE* blocks.

To move code within a file, use 2 *SEARCH/REPLACE* blocks: 1 to delete it from its current location, 1 to insert it in the new location.

Pay attention to which filenames the user wants you to edit.

If you want to put code in a new file or an empty file, use a *SEARCH/REPLACE block* with:
- A new file path, including dir name if needed
- An empty `SEARCH` section
- The new file's contents in the `REPLACE` section

Reply only in English. ONLY EVER RETURN CODE IN A *SEARCH/REPLACE BLOCK*!"""
