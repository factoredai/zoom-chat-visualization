import re
import html
import unicodedata  # Standard library module for Unicode character properties
from collections import defaultdict


def is_emoji_extender(char):
    """
    Checks if a character is a common emoji extender using only the standard library.
    This helps group characters like skin-tone modifiers or Zero-Width Joiners
    with the preceding base emoji.
    """
    # Zero-Width Joiner is the most important for sequences like ❤️‍🔥 or 👨‍👩‍👧‍👦
    if char == "\u200d":
        return True

    # Variation Selectors (especially VS-16 for emoji presentation)
    if "\ufe00" <= char <= "\ufe0f":
        return True

    # Skin Tone Modifiers
    if "\U0001f3fb" <= char <= "\U0001f3ff":
        return True

    # Other common combining marks (like accents)
    if unicodedata.category(char) in ("Mn", "Me", "Mc"):
        return True

    return False


def split_emojis_correctly(text):
    """
    Splits a string containing emojis into a list of proper grapheme clusters.
    This function handles multi-codepoint emojis without external libraries.
    """
    if not text:
        return []

    graphemes = []
    current_grapheme = ""

    for char in text:
        if current_grapheme and (
            is_emoji_extender(char) or current_grapheme[-1] == "\u200d"
        ):
            current_grapheme += char
        else:
            if current_grapheme:
                graphemes.append(current_grapheme)
            current_grapheme = char

    if current_grapheme:
        graphemes.append(current_grapheme)

    return graphemes


def generate_html_for_messages(messages, is_thread=False):
    """Recursively generates HTML for a list of message dictionaries."""
    if not messages:
        return ""

    message_html = ""
    container_class = "thread-container" if is_thread else "chat-container"
    message_html += f'<div class="{container_class}">'

    for msg in messages:
        # --- Message Container ---
        message_html += '<div class="message-bubble">'

        # --- Header (Sender and Timestamp) ---
        message_html += '<div class="message-header">'
        message_html += f'<span class="sender">{html.escape(msg["sender"])}</span>'
        message_html += f'<span class="timestamp">{msg["timestamp"]}</span>'
        message_html += "</div>"

        # --- Message Body ---
        message_body = html.escape(msg["message"]).replace("\n", "<br>")
        message_html += f'<div class="message-body">{message_body}</div>'

        # --- Reactions ---
        if msg["reactions"]:
            message_html += '<div class="reactions">'
            for emoji, reactors in msg["reactions"].items():
                reactor_list = ", ".join(map(html.escape, reactors))
                # Store reactors in a data-attribute:
                message_html += f'<span class="reaction" data-reactors="{reactor_list}">{html.escape(emoji)} <span class="reaction-count">{len(reactors)}</span></span>'
            message_html += "</div>"

        # --- Thread Accordion ---
        if msg.get("thread"):
            thread_count = len(msg["thread"])
            plural_s = "s" if thread_count > 1 else ""
            message_html += '<details class="thread-accordion">'
            message_html += (
                f"<summary>View Thread ({thread_count} repl{plural_s})</summary>"
            )
            message_html += generate_html_for_messages(msg["thread"], is_thread=True)
            message_html += "</details>"

        message_html += "</div>"

    message_html += "</div>"
    return message_html


def parse_chat_log(file, is_path=True):
    """Parses a Zoom chat log file into a structured list of dictionaries."""
    if is_path:
        with open(file, "r", encoding="utf-8") as f:
            lines = f.readlines()
    else:
        lines = file.splitlines()

    message_start_pattern = re.compile(r"^(\d{2}:\d{2}:\d{2}) From (.+?) to Everyone:$")
    reply_pattern = re.compile(r'^\s*Replying to "(.+?)":$')
    reaction_pattern = re.compile(r"^\s*([^:]+?):(.+)$")

    flat_messages = []
    current_message_block = []
    for line in lines:
        if message_start_pattern.match(line) and current_message_block:
            flat_messages.append(current_message_block)
            current_message_block = [line]
        else:
            current_message_block.append(line)
    if current_message_block:
        flat_messages.append(current_message_block)

    parsed_messages = []
    for block in flat_messages:
        msg_obj = {}
        header_match = message_start_pattern.match(block[0])
        if not header_match:
            continue
        msg_obj["timestamp"] = header_match.group(1)
        msg_obj["sender"] = header_match.group(2).strip()
        body_lines = block[1:]
        msg_obj["message"] = ""
        msg_obj["reply_to"] = None
        msg_obj["reactions"] = defaultdict(list)
        msg_obj["thread"] = []
        message_content_lines = []
        for line in body_lines:
            line_stripped = line.strip()
            if not line_stripped:
                continue

            reply_match = reply_pattern.match(line_stripped)
            reaction_match = reaction_pattern.match(line_stripped)

            is_true_reaction = False
            # ===== FIX #1: Stricter Reaction Detection =====
            if reaction_match:
                reactors_str = reaction_match.group(1)
                emojis_str = reaction_match.group(2)

                # Heuristic: A list of reactors is either short (<=5 words) or contains commas.
                # This prevents long sentences from being parsed as reactors.
                is_plausible_reactor_list = (
                    "," in reactors_str or len(reactors_str.split()) <= 5
                )

                # Heuristic: The reaction part should not contain letters.
                is_plausible_emoji_string = not re.search(r"[a-zA-Z]", emojis_str)

                if is_plausible_reactor_list and is_plausible_emoji_string:
                    is_true_reaction = True

            if reply_match:
                msg_obj["reply_to"] = reply_match.group(1)
            elif is_true_reaction:
                reactors_str = reaction_match.group(1)
                emojis_str = reaction_match.group(2).strip()
                reactors = [name.strip() for name in reactors_str.split(",")]
                emojis = split_emojis_correctly(emojis_str)
                for emoji in emojis:
                    msg_obj["reactions"][emoji.strip()].extend(reactors)
            else:
                message_content_lines.append(line.strip("\n"))

        msg_obj["message"] = "\n".join(message_content_lines)

        # Handle tabs at the beginning of the messages:
        if msg_obj["message"].startswith("\t"):
            msg_obj["message"] = msg_obj["message"].lstrip("\t")

        parsed_messages.append(msg_obj)

    structured_messages = []
    content_lookup = {msg["message"]: msg for msg in parsed_messages if msg["message"]}
    for msg in parsed_messages:
        parent = None
        if msg["reply_to"]:
            snippet = msg["reply_to"]
            # ===== FIX #2: Handle Truncated Reply Snippets =====
            # If the snippet from the log is truncated, remove the ellipsis for matching.
            if snippet.endswith("..."):
                snippet = snippet[:-3]

            for content, potential_parent in content_lookup.items():
                if content and content.startswith(snippet):
                    parent = potential_parent
                    break
        if parent:
            parent["thread"].append(msg)
        else:
            structured_messages.append(msg)
    return structured_messages


def main_js():
    import js
    chat_data = parse_chat_log(FILE_TEXT_CONTENT, is_path=False)
    chat_body_html = generate_html_for_messages(chat_data)
    js.document.getElementById("chatLogContainer").innerHTML = (
        "<header> <h1>Zoom Chat Log</h1> </header>" + chat_body_html
    )
