import argparse
import html
from zoom_chat_parser import parse_chat_log, generate_html_for_messages


def generate_html_file(chat_messages, title="Zoom Chat Log"):
    """Generates the full HTML file content as a string."""
    chat_body_html = generate_html_for_messages(chat_messages)
    html_template = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{html.escape(title)}</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;700&display=swap" rel="stylesheet">
    <style>
        :root {{
            --background-color: #f0f2f5; --chat-bubble-bg: #ffffff; --thread-bubble-bg: #f8f9fa;
            --text-primary: #050505; --text-secondary: #65676b; --accent-color: #0078FF;
            --border-color: #e4e6eb; --shadow-color: rgba(0, 0, 0, 0.05);
        }}
        body {{
            font-family: 'Inter', sans-serif; background-color: var(--background-color); color: var(--text-primary);
            margin: 0; padding: 20px; font-size: 15px; line-height: 1.5;
        }}
        .main-container {{
            max-width: 800px; margin: 0 auto; background-color: var(--chat-bubble-bg);
            border-radius: 12px; box-shadow: 0 4px 12px var(--shadow-color); overflow: hidden;
        }}
        header {{ padding: 20px; background-color: var(--accent-color); color: white; text-align: center; }}
        header h1 {{ margin: 0; font-size: 1.5em; }}
        .chat-container {{ padding: 20px; }}
        .message-bubble {{
            background-color: var(--chat-bubble-bg); border: 1px solid var(--border-color);
            border-radius: 12px; padding: 12px 16px; margin-bottom: 12px;
            box-shadow: 0 1px 3px var(--shadow-color);
        }}
        .message-header {{ display: flex; align-items: baseline; margin-bottom: 6px; }}
        .sender {{ font-weight: 700; }}
        .timestamp {{
            font-size: 0.8em;
            color: var(--text-secondary);
            margin-left: 8px;
        }}
        .message-body {{ word-wrap: break-word; }}
        .reactions {{ margin-top: 10px; display: flex; flex-wrap: wrap; gap: 6px; }}
        .reaction {{
            background-color: var(--background-color); border: 1px solid var(--border-color);
            border-radius: 16px; padding: 4px 10px; font-size: 0.9em;
            cursor: default; user-select: none; transition: transform 0.1s ease-in-out;
        }}
        .reaction:hover {{ transform: translateY(-1px); box-shadow: 0 2px 4px var(--shadow-color); }}
        .reaction-count {{ color: var(--text-secondary); font-size: 0.9em; margin-left: 4px; }}
        .thread-accordion {{ margin-top: 12px; border-top: 1px solid var(--border-color); padding-top: 12px; }}
        .thread-accordion summary {{ cursor: pointer; font-weight: 500; color: var(--accent-color); user-select: none; }}
        .thread-accordion summary::marker {{ color: var(--accent-color); }}
        .thread-accordion[open] > summary {{ margin-bottom: 10px; }}
        .thread-container {{ padding-left: 20px; border-left: 2px solid var(--accent-color); margin-top: 10px; }}
        .thread-container .message-bubble {{ background-color: var(--thread-bubble-bg); }}

        /* Custom Tooltip Styles */
        .custom-tooltip {{
            position: absolute;
            background-color: #333; /* Dark background */
            color: white;
            padding: 6px 10px;
            border-radius: 6px;
            font-size: 0.85em;
            z-index: 1000; /* Ensure it's on top */
            /* Removed white-space: nowrap; */
            max-width: 350px; /* Set a max-width to enable wrapping */
            box-shadow: 0 2px 8px rgba(0,0,0,0.2);
            pointer-events: none; /* Allows clicks to pass through to elements behind it */
            opacity: 0;
            transition: opacity 0.1s ease-in-out;
        }}
        .custom-tooltip.show {{
            opacity: 1;
        }}
    </style>
</head>
<body> <div class="main-container"> <header> <h1>{html.escape(title)}</h1> </header> {chat_body_html} </div> 
<script>
    document.addEventListener('DOMContentLoaded', () => {{
        const reactions = document.querySelectorAll('.reaction');
        let showTooltipTimeout;
        let currentTooltip = null; // To keep track of the currently displayed tooltip

        reactions.forEach(reaction => {{
            reaction.addEventListener('mouseover', () => {{ // Removed 'event' parameter as it's not strictly needed here
                // Use 'reaction' directly, which is the element the listener is attached to.
                const reactorNames = reaction.dataset.reactors;
                if (!reactorNames) return;

                // Clear any pending timeout and hide any existing tooltip immediately
                clearTimeout(showTooltipTimeout);
                if (currentTooltip) {{
                    currentTooltip.remove();
                    currentTooltip = null;
                }}

                // Set a timeout to show the tooltip after a short delay (e.g., 100ms)
                showTooltipTimeout = setTimeout(() => {{
                    // Double-check if the 'reaction' element is still in the DOM
                    // This can happen if the element was removed before the timeout fires
                    if (!document.body.contains(reaction)) {{
                        return;
                    }}

                    const tooltip = document.createElement('div');
                    tooltip.classList.add('custom-tooltip');
                    tooltip.textContent = `Reacted by: ${{reactorNames}}`;
                    document.body.appendChild(tooltip); // Append to body for global positioning
                    currentTooltip = tooltip; // Store reference to current tooltip

                    // Position the tooltip relative to the hovered reaction element
                    const rect = reaction.getBoundingClientRect(); // <--- Changed from event.currentTarget
                    tooltip.style.left = `${{rect.left + window.scrollX}}px`;
                    // Position 8px below the reaction
                    tooltip.style.top = `${{rect.bottom + window.scrollY + 8}}px`;
                    tooltip.classList.add('show'); // Trigger opacity transition
                }}, 100); // Adjust this delay (in milliseconds) as desired
            }});

            reaction.addEventListener('mouseout', () => {{
                clearTimeout(showTooltipTimeout); // Clear the show timeout
                if (currentTooltip) {{
                    currentTooltip.classList.remove('show');
                    setTimeout(() => {{
                        if (currentTooltip) {{
                            currentTooltip.remove();
                            currentTooltip = null;
                        }}
                    }}, 150); // Small delay for fade-out transition
                }}
            }});

            // Optional: Hide tooltip if mouse leaves the document or scrolls significantly
            document.addEventListener('scroll', () => {{
                if (currentTooltip) {{
                    currentTooltip.remove();
                    currentTooltip = null;
                    clearTimeout(showTooltipTimeout);
                }}
            }});
        }});
    }});
</script>
</body>
</html>
"""
    return html_template


def main():
    """Main function to run the script from the command line."""
    parser = argparse.ArgumentParser(
        description="Convert a Zoom chat log .txt file into a styled HTML file.",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("input_file", help="Path to the input Zoom chat .txt file.")
    parser.add_argument("output_file", help="Path for the output .html file.")
    parser.add_argument(
        "-t", "--title", default="Zoom Chat Log", help="The title of the HTML document."
    )
    args = parser.parse_args()
    try:
        print(f"Parsing '{args.input_file}'...")
        chat_data = parse_chat_log(args.input_file)
        print("Generating HTML...")
        html_content = generate_html_file(chat_data, title=args.title)
        with open(args.output_file, "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"\nSuccess! Chat log has been converted to '{args.output_file}'")
    except FileNotFoundError:
        print(f"Error: The file '{args.input_file}' was not found.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")


if __name__ == "__main__":
    main()