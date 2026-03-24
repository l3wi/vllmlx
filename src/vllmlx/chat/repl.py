"""Interactive daemon-backed chat REPL for vllmlx."""

from __future__ import annotations

import json
from typing import Optional

import httpx
from rich.console import Console

console = Console()


class ChatSession:
    """Interactive chat session with the vllmlx daemon."""

    def __init__(self, model: str, api_url: str = "http://127.0.0.1:8000"):
        self.model = model
        self.api_url = api_url
        self.messages: list[dict] = []
        self.running = True

    def add_user_message(self, content: str) -> None:
        self.messages.append({"role": "user", "content": content})

    def add_assistant_message(self, content: str) -> None:
        self.messages.append({"role": "assistant", "content": content})

    def clear_history(self) -> None:
        self.messages = []
        console.print("[dim]Conversation cleared[/dim]")

    def send_message(self, content: str) -> Optional[str]:
        """Send a user message and stream response from daemon."""
        self.add_user_message(content)

        try:
            with httpx.stream(
                "POST",
                f"{self.api_url}/v1/chat/completions",
                json={
                    "model": self.model,
                    "messages": self.messages,
                    "stream": True,
                    "max_tokens": 1024,
                },
                timeout=None,
            ) as response:
                if response.status_code != 200:
                    error = response.read().decode()
                    console.print(f"[red]Error: {error}[/red]")
                    self.messages.pop()
                    return None

                full_response = self._stream_response(response)
                self.add_assistant_message(full_response)
                return full_response

        except httpx.ConnectError:
            console.print("[red]Error: Cannot connect to daemon. Is it running?[/red]")
            console.print("[dim]Try: vllmlx daemon start[/dim]")
            self.messages.pop()
            return None
        except httpx.HTTPError as e:
            console.print(f"[red]Error: Streaming failed ({e})[/red]")
            self.messages.pop()
            return None
        except KeyboardInterrupt:
            console.print("\n[dim]Response cancelled[/dim]")
            self.messages.pop()
            return None

    def _stream_response(self, response: httpx.Response) -> str:
        """Render streamed SSE chunks to terminal."""
        full_text = ""

        console.print()

        for line in response.iter_lines():
            if not line or line.startswith(":"):
                continue

            if line.startswith("data: "):
                data = line[6:]
                if data == "[DONE]":
                    break

                try:
                    chunk = json.loads(data)
                    delta = chunk.get("choices", [{}])[0].get("delta", {})
                    content = delta.get("content", "")
                    if content:
                        console.print(content, end="")
                        full_text += content
                except json.JSONDecodeError:
                    pass

        console.print()
        console.print()

        return full_text

    def handle_command(self, cmd: str) -> bool:
        cmd = cmd.lower().strip()

        if cmd in ("/exit", "/quit", "/q"):
            return False
        if cmd == "/clear":
            self.clear_history()
            return True
        if cmd == "/help":
            self._show_help()
            return True
        if cmd == "/history":
            self._show_history()
            return True

        console.print(f"[yellow]Unknown command: {cmd}[/yellow]")
        console.print("[dim]Type /help for available commands[/dim]")
        return True

    def _show_help(self) -> None:
        console.print(
            """
[bold]Commands:[/bold]
  /clear    - Clear conversation history
  /history  - Show conversation history
  /exit     - Exit chat session (or /quit, /q)
  /help     - Show this help
        """
        )

    def _show_history(self) -> None:
        if not self.messages:
            console.print("[dim]No messages in history[/dim]")
            return

        for msg in self.messages:
            role = msg["role"]
            content = msg["content"]
            if role == "user":
                console.print(f"[cyan]You:[/cyan] {content}")
            else:
                display_content = content[:100] + "..." if len(content) > 100 else content
                console.print(f"[green]Assistant:[/green] {display_content}")

    def run(self) -> None:
        self._show_welcome()

        while self.running:
            try:
                user_input = console.input("[bold cyan]> [/bold cyan]").strip()

                if not user_input:
                    continue

                if user_input.startswith("/"):
                    if not self.handle_command(user_input):
                        break
                    continue

                self.send_message(user_input)

            except KeyboardInterrupt:
                console.print("\n[dim]Use /exit to quit[/dim]")
            except EOFError:
                break

        console.print("[dim]Goodbye![/dim]")

    def _show_welcome(self) -> None:
        console.print(
            f"""
[bold]vllmlx chat[/bold] - Model: [cyan]{self.model}[/cyan]
Type your message and press Enter. Use /help for commands.
"""
        )


def start_chat(model: str, api_url: str = "http://127.0.0.1:8000") -> None:
    """Start an interactive chat session via daemon API."""
    session = ChatSession(model, api_url)
    session.run()
