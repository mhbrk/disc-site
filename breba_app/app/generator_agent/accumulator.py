import re


class TagAccumulator:
    CLOSE_TAG_RE = re.compile(r"</[^>]+>")

    def __init__(self):
        self.buffer = ""
        self.done = False

    def append_and_return_html(self, chunk: str) -> str:
        """
        Returns a single string containing everything in the buffer
        up to and including the last matched closing tag (</...>).
        Clears that part from the buffer.
        """
        if self.done:
            return ""
        self.buffer += chunk

        matches = list(self.CLOSE_TAG_RE.finditer(self.buffer))
        if not matches:
            return ""

        last_match = matches[-1]
        end = last_match.end()
        result = self.buffer[:end]
        if "</html>" in result:
            self.done = True
        self.buffer = self.buffer[end:]
        return result

    def drain_buffer(self) -> str:
        """
        Returns whatever remains in the buffer and clears it.
        """
        leftover = self.buffer
        self.buffer = ""
        return leftover
