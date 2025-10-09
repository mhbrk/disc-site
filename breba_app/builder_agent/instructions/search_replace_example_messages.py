example_messages = [
    dict(
        role="user",
        content="Change get_factorial() to use math.factorial",
    ),
    dict(
        role="assistant",
        content="""To make this change we need to modify to:

1. Import the math package.
2. Remove the existing factorial() function.
3. Update get_factorial() to call math.factorial instead.

Here are the *SEARCH/REPLACE* blocks:

mathweb/flask/app.md
```markdown
<<<<<<< SEARCH
from flask import Flask
=======
import math
from flask import Flask
>>>>>>> REPLACE
```

mathweb/flask/app.md
```markdown
<<<<<<< SEARCH
def factorial(n):
    "compute factorial"

    if n == 0:
        return 1
    else:
        return n * factorial(n-1)

=======
>>>>>>> REPLACE
```

mathweb/flask/app.md
```markdown
<<<<<<< SEARCH
    return str(factorial(n))
=======
    return str(math.factorial(n))
>>>>>>> REPLACE
```
""",
    ),
    dict(
        role="user",
        content="Refactor hello() into its own file.",
    ),
    dict(
        role="assistant",
        content="""To make this change we need to modify `main.md` and make a new file `hello.md`:

1. Make a new hello.md file with hello() in it.
2. Remove hello() from main.md and replace it with an import.

Here are the *SEARCH/REPLACE* blocks:

hello.md
```markdown
<<<<<<< SEARCH
=======
def hello():
    "print a greeting"

    print("hello")
>>>>>>> REPLACE
```

main.md
```markdown
<<<<<<< SEARCH
def hello():
    "print a greeting"

    print("hello")
=======
from hello import hello
>>>>>>> REPLACE
```
""",
    ),
]
