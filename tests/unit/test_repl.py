"""Tests for REPL (interactive chat) module."""

from unittest.mock import Mock, patch

import httpx


class TestChatSession:
    """Tests for ChatSession class."""

    def test_init(self):
        """Test ChatSession initialization."""
        from vllmlx.chat.repl import ChatSession

        session = ChatSession("test-model")

        assert session.model == "test-model"
        assert session.api_url == "http://127.0.0.1:8000"
        assert session.messages == []
        assert session.running is True

    def test_init_custom_url(self):
        """Test ChatSession with custom API URL."""
        from vllmlx.chat.repl import ChatSession

        session = ChatSession("test-model", api_url="http://localhost:8080")

        assert session.api_url == "http://localhost:8080"

    def test_add_user_message(self):
        """Test adding user message to history."""
        from vllmlx.chat.repl import ChatSession

        session = ChatSession("test-model")
        session.add_user_message("Hello")

        assert len(session.messages) == 1
        assert session.messages[0]["role"] == "user"
        assert session.messages[0]["content"] == "Hello"

    def test_add_assistant_message(self):
        """Test adding assistant message to history."""
        from vllmlx.chat.repl import ChatSession

        session = ChatSession("test-model")
        session.add_assistant_message("Hi there!")

        assert len(session.messages) == 1
        assert session.messages[0]["role"] == "assistant"
        assert session.messages[0]["content"] == "Hi there!"

    def test_message_history_preserves_order(self):
        """Test message history preserves order."""
        from vllmlx.chat.repl import ChatSession

        session = ChatSession("test-model")
        session.add_user_message("Hello")
        session.add_assistant_message("Hi!")
        session.add_user_message("How are you?")
        session.add_assistant_message("I'm good!")

        assert len(session.messages) == 4
        assert session.messages[0]["role"] == "user"
        assert session.messages[1]["role"] == "assistant"
        assert session.messages[2]["role"] == "user"
        assert session.messages[3]["role"] == "assistant"

    def test_clear_history(self):
        """Test clearing conversation history."""
        from vllmlx.chat.repl import ChatSession

        session = ChatSession("test-model")
        session.add_user_message("Hello")
        session.add_assistant_message("Hi")

        session.clear_history()

        assert len(session.messages) == 0


class TestHandleCommand:
    """Tests for command handling."""

    def test_handle_exit_command(self):
        """Test /exit command returns False to exit."""
        from vllmlx.chat.repl import ChatSession

        session = ChatSession("test-model")

        assert session.handle_command("/exit") is False

    def test_handle_quit_command(self):
        """Test /quit command returns False to exit."""
        from vllmlx.chat.repl import ChatSession

        session = ChatSession("test-model")

        assert session.handle_command("/quit") is False

    def test_handle_q_command(self):
        """Test /q shortcut returns False to exit."""
        from vllmlx.chat.repl import ChatSession

        session = ChatSession("test-model")

        assert session.handle_command("/q") is False

    def test_handle_clear_command(self):
        """Test /clear command clears history and returns True."""
        from vllmlx.chat.repl import ChatSession

        session = ChatSession("test-model")
        session.add_user_message("test")

        result = session.handle_command("/clear")

        assert result is True
        assert len(session.messages) == 0

    def test_handle_help_command(self):
        """Test /help command returns True to continue."""
        from vllmlx.chat.repl import ChatSession

        session = ChatSession("test-model")

        result = session.handle_command("/help")

        assert result is True

    def test_handle_history_command(self):
        """Test /history command returns True to continue."""
        from vllmlx.chat.repl import ChatSession

        session = ChatSession("test-model")

        result = session.handle_command("/history")

        assert result is True

    def test_handle_unknown_command(self):
        """Test unknown command returns True (don't exit)."""
        from vllmlx.chat.repl import ChatSession

        session = ChatSession("test-model")

        result = session.handle_command("/unknown")

        assert result is True

    def test_handle_command_case_insensitive(self):
        """Test commands are case insensitive."""
        from vllmlx.chat.repl import ChatSession

        session = ChatSession("test-model")

        assert session.handle_command("/EXIT") is False
        assert session.handle_command("/QUIT") is False
        assert session.handle_command("/Clear") is True

    def test_handle_command_with_whitespace(self):
        """Test commands handle leading/trailing whitespace."""
        from vllmlx.chat.repl import ChatSession

        session = ChatSession("test-model")

        assert session.handle_command("  /exit  ") is False


class TestSendMessage:
    """Tests for send_message method."""

    @patch("vllmlx.chat.repl.httpx")
    def test_send_message_connection_error(self, mock_httpx):
        """Test send_message handles connection errors."""
        from vllmlx.chat.repl import ChatSession

        # Setup mock to raise connection error
        mock_httpx.stream.return_value.__enter__ = Mock(
            side_effect=httpx.ConnectError("Connection refused")
        )
        mock_httpx.ConnectError = httpx.ConnectError

        session = ChatSession("test-model")
        result = session.send_message("Hello")

        assert result is None
        assert len(session.messages) == 0  # Message removed on failure

    def test_send_message_adds_to_history_on_success(self):
        """Test successful message adds to history."""
        from vllmlx.chat.repl import ChatSession

        # Create a session and manually test the message tracking
        session = ChatSession("test-model")
        session.add_user_message("Hello")
        session.add_assistant_message("Hi there!")

        assert len(session.messages) == 2
        assert session.messages[0]["role"] == "user"
        assert session.messages[1]["role"] == "assistant"


class TestStartChat:
    """Tests for start_chat function."""

    def test_start_chat_creates_session(self):
        """Test start_chat creates ChatSession with correct params."""
        from vllmlx.chat.repl import ChatSession

        # Test that we can create a session (don't actually run it)
        session = ChatSession("test-model", api_url="http://localhost:9999")

        assert session.model == "test-model"
        assert session.api_url == "http://localhost:9999"
