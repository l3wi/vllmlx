# Task: Interactive Chat

**Phase**: 5  
**Branch**: `feat/vmlx-phase-5`  
**Plan**: [docs/plans/vmlx.md](../plans/vmlx.md)  
**Spec**: [docs/specs/vmlx-spec.md](../specs/vmlx-spec.md)  
**Status**: pending  
**Parallel With**: Phase 3, Phase 4

---

## Objective

Implement simple interactive chat REPL via `vmlx run <model>` that connects to the daemon API with streaming output.

---

## Acceptance Criteria

- [ ] `vmlx run qwen2-vl-7b` starts interactive chat session
- [ ] `vmlx run` without model uses config default (if set)
- [ ] Simple `> ` prompt accepts text input
- [ ] Responses stream to terminal in real-time
- [ ] Multi-line input supported (paste or Shift+Enter awareness)
- [ ] Ctrl+C cleanly exits session
- [ ] Ctrl+C during generation cancels current response
- [ ] `/exit` or `/quit` commands exit session
- [ ] `/clear` clears conversation history
- [ ] Shows helpful startup message with model name
- [ ] Error messages for daemon not running, model not found
- [ ] All tests pass
- [ ] Lint clean

---

## Files to Create

| File | Action | Description |
|------|--------|-------------|
| `src/vmlx/cli/run.py` | create | `vmlx run` command |
| `src/vmlx/chat/__init__.py` | create | Chat module init |
| `src/vmlx/chat/repl.py` | create | REPL implementation |
| `tests/unit/test_repl.py` | create | REPL logic tests |

---

## Implementation Notes

### REPL Module (repl.py)

```python
import sys
import httpx
from typing import Optional, List
from rich.console import Console
from rich.markdown import Markdown
from rich.live import Live

console = Console()

class ChatSession:
    """Interactive chat session with the vmlx daemon."""
    
    def __init__(self, model: str, api_url: str = "http://127.0.0.1:11434"):
        self.model = model
        self.api_url = api_url
        self.messages: List[dict] = []
        self.running = True
    
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
        """Send message to API and stream response."""
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
        """Stream SSE response and print tokens."""
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
                    import json
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
        """Handle special commands. Returns False if should exit."""
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
        console.print("""
[bold]Commands:[/bold]
  /clear    - Clear conversation history
  /history  - Show conversation history
  /exit     - Exit chat session
  /help     - Show this help
        """)
    
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
                console.print(f"[green]Assistant:[/green] {content[:100]}...")
    
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
        console.print(f"""
[bold]vmlx chat[/bold] - Model: [cyan]{self.model}[/cyan]
Type your message and press Enter. Use /help for commands.
""")


def start_chat(model: str, api_url: str = "http://127.0.0.1:11434") -> None:
    """Start an interactive chat session."""
    session = ChatSession(model, api_url)
    session.run()
```

### Run Command (run.py)

```python
import click
from rich.console import Console

console = Console()

@click.command()
@click.argument("model", required=False)
def run(model: str = None):
    """Start an interactive chat session.
    
    MODEL is the model name or alias (e.g., qwen2-vl-7b).
    If not provided, uses the default model from config.
    """
    from vmlx.config import Config
    from vmlx.models.aliases import resolve_alias
    from vmlx.chat.repl import start_chat
    import httpx
    
    config = Config.load()
    
    # Determine model to use
    if not model:
        if config.models.default:
            model = config.models.default
        else:
            console.print("[red]Error: No model specified and no default set[/red]")
            console.print("[dim]Usage: vmlx run <model>[/dim]")
            console.print("[dim]Or set default: vmlx config set models.default qwen2-vl-7b[/dim]")
            raise SystemExit(1)
    
    # Resolve alias
    model_path = resolve_alias(model, config.aliases)
    
    # Check daemon is running
    api_url = f"http://{config.daemon.host}:{config.daemon.port}"
    try:
        response = httpx.get(f"{api_url}/health", timeout=2.0)
        if response.status_code != 200:
            raise httpx.ConnectError("Unhealthy")
    except (httpx.ConnectError, httpx.TimeoutException):
        console.print("[red]Error: Daemon is not running[/red]")
        console.print("[dim]Start it with: vmlx daemon start[/dim]")
        raise SystemExit(1)
    
    # Start chat
    start_chat(model_path, api_url)
```

### Register Command (main.py)

```python
from vmlx.cli.run import run

cli.add_command(run)
```

### Input Handling Notes

For simple readline-style input:
- `console.input()` from Rich handles basic line editing
- Ctrl+C raises KeyboardInterrupt (catch and handle)
- EOFError on Ctrl+D (exit gracefully)

For multi-line paste:
- Rich's input handles pasted text as single input
- No special handling needed for basic paste

---

## Testing Requirements

### Unit Tests (test_repl.py)

```python
import pytest
from unittest.mock import Mock, patch
from vmlx.chat.repl import ChatSession

def test_add_user_message():
    session = ChatSession("test-model")
    session.add_user_message("Hello")
    
    assert len(session.messages) == 1
    assert session.messages[0]["role"] == "user"
    assert session.messages[0]["content"] == "Hello"

def test_add_assistant_message():
    session = ChatSession("test-model")
    session.add_assistant_message("Hi there!")
    
    assert len(session.messages) == 1
    assert session.messages[0]["role"] == "assistant"

def test_clear_history():
    session = ChatSession("test-model")
    session.add_user_message("Hello")
    session.add_assistant_message("Hi")
    
    session.clear_history()
    
    assert len(session.messages) == 0

def test_handle_exit_command():
    session = ChatSession("test-model")
    
    assert session.handle_command("/exit") == False
    assert session.handle_command("/quit") == False
    assert session.handle_command("/q") == False

def test_handle_clear_command():
    session = ChatSession("test-model")
    session.add_user_message("test")
    
    result = session.handle_command("/clear")
    
    assert result == True
    assert len(session.messages) == 0

def test_handle_unknown_command():
    session = ChatSession("test-model")
    
    result = session.handle_command("/unknown")
    
    assert result == True  # Don't exit on unknown command

@patch("vmlx.chat.repl.httpx")
def test_send_message_connection_error(mock_httpx):
    mock_httpx.stream.side_effect = httpx.ConnectError("Connection refused")
    
    session = ChatSession("test-model")
    result = session.send_message("Hello")
    
    assert result is None
    assert len(session.messages) == 0  # Message removed on failure
```

---

## Agent Instructions

1. Create `chat/` module with `repl.py`
2. Implement `ChatSession` class with message history
3. Implement streaming response display
4. Add command handling (`/exit`, `/clear`, `/help`, `/history`)
5. Create `run.py` CLI command
6. Register in main CLI
7. Write unit tests for session logic (mock HTTP)
8. Test manually:
   ```bash
   vmlx daemon start
   vmlx run qwen2-vl-2b
   > Hello, what can you do?
   [streaming response...]
   > /help
   > /clear
   > /exit
   ```
9. Test error cases:
   ```bash
   vmlx daemon stop
   vmlx run qwen2-vl-2b  # Should show "daemon not running"
   ```
10. Run `ruff check` and `pytest`
11. Commit with `wt commit`
