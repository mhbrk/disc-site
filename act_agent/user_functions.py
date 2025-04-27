import json
from typing import Any, Callable, Set, Optional


def save_data(data: Optional[str] = None) -> str:
    """
    Saves data to a file. Use this when the user wants to save some information.

    :param data (Optional[str]): The data to save
    :return: A JSON string indicating success or failure.
    :rtype: str
    """
    if data:
        with open("data.txt", "w") as f:
            f.write(data)
    return json.dumps({"success": True})


def send_email(recipient: str, subject: str, body: str) -> str:
    """
    Sends an email with the specified subject and body to the recipient.

    :param recipient (str): Email address of the recipient.
    :param subject (str): Subject of the email.
    :param body (str): Body content of the email.
    :return: Confirmation message.
    :rtype: str
    """
    print(f"Sending email to {recipient}...")
    print(f"Subject: {subject}")
    print(f"Body:\n{body}")

    message_json = json.dumps({"message": f"Email successfully sent to {recipient}."})
    return message_json


user_functions: Set[Callable[..., Any]] = {
    send_email,
    save_data,
}
