example_messages = [
    dict(
        role="user",
        content="Change the button text from 'Submit' to 'Send'",
    ),
    dict(
        role="assistant",
        content="""To make this change we need to modify to:
spec.md
```markdown
<<<<<<< SEARCH
### Form
- Button: `Submit`. On click, submit the form payload to the `/submit` endpoint
=======
### Form
- Button: `Send`. On click, submit the form payload to the `/submit` endpoint
>>>>>>> REPLACE
```

spec.md
```markdown
<<<<<<< SEARCH
- The `Submit` button and the `Clear form` button need to be full width in mobile an stacked on top of each other
=======
- The `Send` button and the `Clear form` button need to be full width in mobile an stacked on top of each other
>>>>>>> REPLACE
```

spec.md
```markdown
<<<<<<< SEARCH
    - When the `Submit` button is clicked, make sure the form is greyed out and a spinner shows up while waiting for response
=======
    - When the `Send` button is clicked, make sure the form is greyed out and a spinner shows up while waiting for response
>>>>>>> REPLACE
```
""",
    ),
    dict(
        role="user",
        content="I want to build a simple Hello World website",
    ),
    dict(
        role="assistant",
        content="""To make this change we need to start with a clean `spec.md`:
Here are the *SEARCH/REPLACE* blocks:

hello.md
```markdown
<<<<<<< SEARCH
=======
# "Hello World" Website Specification

## Content
- Text: `Hello World`

## Visual
- Center text vertically and horizontally.

## Implementation
- Pure HTML with minimal inline CSS only; no external CSS/JS.
- Ensure responsiveness: centering works at all viewport sizes.
>>>>>>> REPLACE
```
""",
    ),
]

system_reminder = """# *SEARCH/REPLACE block* Rules:

Every *SEARCH/REPLACE block* must use this format:
1. The *FULL* file path alone on a line, verbatim. No bold asterisks, no quotes around it, no escaping of characters, etc.
2. The opening fence and code language, eg: ```markdown
3. The start of search block: <<<<<<< SEARCH
4. A contiguous chunk of lines to search for in the existing source code
5. The dividing line: =======
6. The lines to replace into the source code
7. The end of the replace block: >>>>>>> REPLACE
8. The closing fence: ```

Use the *FULL* file path, as shown to you by the user.

Every *SEARCH* section must *EXACTLY MATCH* the existing file content, character for character, including all comments, docstrings, etc.
If the file contains code or other data wrapped/escaped in json/xml/quotes or other containers, you need to propose edits to the literal contents of the file, including the container markup.
You are always editing spec.md.

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

Reply only in English. ONLY EVER RETURN CODE IN A *SEARCH/REPLACE BLOCK*!
"""
