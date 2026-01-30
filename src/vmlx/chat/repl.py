"""Interactive chat REPL for vmlx."""

import json
from typing import List, Optional, Any

import httpx
from rich.console import Console
from rich.live import Live
from rich.spinner import Spinner

console = Console()


class LocalChatSession:
    """Interactive chat session loading model directly (no daemon)."""

    def __init__(self, model_path: str):
        """Initialize local chat session.

        Args:
            model_path: Full HuggingFace model path
        """
        self.model_path = model_path
        self.model: Any = None
        self.processor: Any = None
        self.config: Any = None
        self.messages: List[dict] = []
        self.running = True

    def load_model(self) -> bool:
        """Load the model using MLX-VLM.
        
        Returns:
            True if loaded successfully
        """
        import sys
        import io
        import warnings
        
        try:
            # Suppress all the noisy warnings during load
            warnings.filterwarnings("ignore")
            
            from mlx_vlm import load
            from mlx_vlm.utils import load_config
            
            console.print(f"[bold blue]Loading {self.model_path}...[/bold blue]")
            
            # Capture stderr to hide progress bars and warnings
            old_stderr = sys.stderr
            sys.stderr = io.StringIO()
            
            try:
                self.model, self.processor = load(self.model_path)
                self.config = load_config(self.model_path)
            finally:
                sys.stderr = old_stderr
            
            console.print(f"[green]✓ Model loaded[/green]\n")
            return True
        except Exception as e:
            console.print(f"[red]Error loading model: {e}[/red]")
            return False

    def unload_model(self) -> None:
        """Unload model and free memory."""
        import gc
        try:
            import mlx.core as mx
            if self.model:
                del self.model
                del self.processor
                del self.config
                self.model = None
                self.processor = None
                self.config = None
                gc.collect()
                # Use new API if available, fallback to old
                if hasattr(mx, 'clear_cache'):
                    mx.clear_cache()
                elif hasattr(mx.metal, 'clear_cache'):
                    mx.metal.clear_cache()
        except Exception:
            pass

    def add_user_message(self, content: str) -> None:
        """Add a user message to history."""
        self.messages.append({"role": "user", "content": content})

    def add_assistant_message(self, content: str) -> None:
        """Add an assistant message to history."""
        self.messages.append({"role": "assistant", "content": content})

    def clear_history(self) -> None:
        """Clear conversation history."""
        self.messages = []
        console.print("[dim]Conversation cleared[/dim]")

    def send_message(self, content: str) -> Optional[str]:
        """Generate response directly using MLX-VLM.

        Args:
            content: User message content

        Returns:
            Full response text or None if failed
        """
        import sys
        import io
        import warnings
        
        from mlx_vlm import generate
        from mlx_vlm.prompt_utils import apply_chat_template

        self.add_user_message(content)

        try:
            # Build prompt from message history
            # For simplicity, just use the latest message
            formatted_prompt = apply_chat_template(
                self.processor, self.config, content, num_images=0
            )

            console.print()  # Newline before response
            full_text = ""

            # Suppress deprecation warnings during generation
            warnings.filterwarnings("ignore")
            
            # Capture stdout/stderr to hide mlx deprecation warnings
            old_stdout = sys.stdout
            old_stderr = sys.stderr
            sys.stdout = io.StringIO()
            sys.stderr = io.StringIO()
            
            try:
                response = generate(
                    self.model,
                    self.processor,
                    formatted_prompt,
                    [],  # no images
                    max_tokens=1024,
                    temp=0.7,
                    verbose=False,
                )
            finally:
                sys.stdout = old_stdout
                sys.stderr = old_stderr
            
            # Print the response
            console.print(response)
            full_text = response

            console.print()  # Newline after response
            console.print()  # Extra spacing

            self.add_assistant_message(full_text)
            return full_text

        except KeyboardInterrupt:
            console.print("\n[dim]Response cancelled[/dim]")
            self.messages.pop()  # Remove cancelled message
            return None
        except Exception as e:
            console.print(f"\n[red]Error: {e}[/red]")
            self.messages.pop()
            return None

    def handle_command(self, cmd: str) -> bool:
        """Handle special commands."""
        cmd = cmd.lower().strip()

        if cmd in ("/exit", "/quit", "/q"):
            return False
        elif cmd == "/clear":
            self.clear_history()
        elif cmd == "/help":
            self._show_help()
        elif cmd == "/history":
            self._show_history()
        else:
            console.print(f"[yellow]Unknown command: {cmd}[/yellow]")
            console.print("[dim]Type /help for available commands[/dim]")

        return True

    def _show_help(self) -> None:
        """Show help message."""
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
        """Show conversation history."""
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
        """Run the interactive chat loop."""
        if not self.load_model():
            return

        self._show_welcome()

        try:
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
        finally:
            self.unload_model()

        console.print("[dim]Goodbye![/dim]")

    def _show_welcome(self) -> None:
        """Show welcome message."""
        console.print(
            f"""
[bold]vmlx chat[/bold] - Model: [cyan]{self.model_path}[/cyan]
Type your message and press Enter. Use /help for commands.
"""
        )


class ChatSession:
    """Interactive chat session with the vmlx daemon."""

    def __init__(self, model: str, api_url: str = "http://127.0.0.1:11434"):
        """Initialize chat session.

        Args:
            model: Model name or alias
            api_url: Daemon API URL
        """
        self.model = model
        self.api_url = api_url
        self.messages: List[dict] = []
        self.running = True

    def add_user_message(self, content: str) -> None:
        """Add a user message to history.

        Args:
            content: Message content
        """
        self.messages.append({"role": "user", "content": content})

    def add_assistant_message(self, content: str) -> None:
        """Add an assistant message to history.

        Args:
            content: Message content
        """
        self.messages.append({"role": "assistant", "content": content})

    def clear_history(self) -> None:
        """Clear conversation history."""
        self.messages = []
        console.print("[dim]Conversation cleared[/dim]")

    def send_message(self, content: str) -> Optional[str]:
        """Send message to API and stream response.

        Args:
            content: User message content

        Returns:
            Full response text or None if failed
        """
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
                timeout=None,  # Streaming can take a while
            ) as response:
                if response.status_code != 200:
                    error = response.read().decode()
                    console.print(f"[red]Error: {error}[/red]")
                    self.messages.pop()  # Remove failed message
                    return None

                full_response = self._stream_response(response)
                self.add_assistant_message(full_response)
                return full_response

        except httpx.ConnectError:
            console.print("[red]Error: Cannot connect to daemon. Is it running?[/red]")
            console.print("[dim]Try: vmlx daemon start[/dim]")
            self.messages.pop()  # Remove failed message
            return None
        except KeyboardInterrupt:
            console.print("\n[dim]Response cancelled[/dim]")
            self.messages.pop()  # Remove cancelled message
            return None

    def _stream_response(self, response: httpx.Response) -> str:
        """Stream SSE response and print tokens.

        Args:
            response: HTTP response object

        Returns:
            Full response text
        """
        full_text = ""

        console.print()  # Newline before response

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

        console.print()  # Newline after response
        console.print()  # Extra spacing

        return full_text

    def handle_command(self, cmd: str) -> bool:
        """Handle special commands.

        Args:
            cmd: Command string (e.g., "/exit")

        Returns:
            False if should exit, True to continue
        """
        cmd = cmd.lower().strip()

        if cmd in ("/exit", "/quit", "/q"):
            return False
        elif cmd == "/clear":
            self.clear_history()
        elif cmd == "/help":
            self._show_help()
        elif cmd == "/history":
            self._show_history()
        else:
            console.print(f"[yellow]Unknown command: {cmd}[/yellow]")
            console.print("[dim]Type /help for available commands[/dim]")

        return True

    def _show_help(self) -> None:
        """Show help message."""
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
        """Show conversation history."""
        if not self.messages:
            console.print("[dim]No messages in history[/dim]")
            return

        for msg in self.messages:
            role = msg["role"]
            content = msg["content"]
            if role == "user":
                console.print(f"[cyan]You:[/cyan] {content}")
            else:
                # Truncate long responses
                display_content = content[:100] + "..." if len(content) > 100 else content
                console.print(f"[green]Assistant:[/green] {display_content}")

    def run(self) -> None:
        """Run the interactive chat loop."""
        self._show_welcome()

        while self.running:
            try:
                # Get user input
                user_input = console.input("[bold cyan]> [/bold cyan]").strip()

                if not user_input:
                    continue

                # Check for commands
                if user_input.startswith("/"):
                    if not self.handle_command(user_input):
                        break
                    continue

                # Send message
                self.send_message(user_input)

            except KeyboardInterrupt:
                console.print("\n[dim]Use /exit to quit[/dim]")
            except EOFError:
                break

        console.print("[dim]Goodbye![/dim]")

    def _show_welcome(self) -> None:
        """Show welcome message."""
        console.print(
            f"""
[bold]vmlx chat[/bold] - Model: [cyan]{self.model}[/cyan]
Type your message and press Enter. Use /help for commands.
"""
        )


def start_chat(model: str, api_url: str = "http://127.0.0.1:11434") -> None:
    """Start an interactive chat session via daemon API.

    Args:
        model: Model name or alias
        api_url: Daemon API URL
    """
    session = ChatSession(model, api_url)
    session.run()


def start_local_chat(model_path: str) -> None:
    """Start an interactive chat session loading model directly.

    Args:
        model_path: Full HuggingFace model path
    """
    session = LocalChatSession(model_path)
    session.run()
