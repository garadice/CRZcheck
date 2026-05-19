"""Tests for app.db.session — engine, session factory, and session generator."""

from __future__ import annotations

import contextlib
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import sessionmaker

from app.db import session as session_module


@pytest.fixture(autouse=True)
def _reset_engine():
    """Reset the global engine singleton between tests."""
    original = session_module._engine
    session_module._engine = None
    yield
    session_module._engine = original


class TestGetEngine:
    @patch("app.db.session.create_engine")
    @patch("app.db.session.settings")
    def test_creates_engine_with_correct_url(self, mock_settings, mock_create_engine):
        mock_settings.database_url = "postgresql://user:pass@localhost/testdb"
        mock_settings.sql_echo = False
        mock_engine = MagicMock(spec=Engine)
        mock_create_engine.return_value = mock_engine

        engine = session_module.get_engine()

        mock_create_engine.assert_called_once_with(
            "postgresql://user:pass@localhost/testdb",
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
            pool_recycle=300,
            connect_args={"connect_timeout": 10},
            echo=False,
        )
        assert engine is mock_engine

    @patch("app.db.session.create_engine")
    @patch("app.db.session.settings")
    def test_cached_on_second_call(self, mock_settings, mock_create_engine):
        mock_settings.database_url = "sqlite:///:memory:"
        mock_settings.sql_echo = False
        mock_engine = MagicMock(spec=Engine)
        mock_create_engine.return_value = mock_engine

        engine1 = session_module.get_engine()
        engine2 = session_module.get_engine()

        # create_engine should only be called once
        assert mock_create_engine.call_count == 1
        assert engine1 is engine2

    @patch("app.db.session.create_engine")
    @patch("app.db.session.settings")
    def test_echo_setting_respected(self, mock_settings, mock_create_engine):
        mock_settings.database_url = "sqlite:///:memory:"
        mock_settings.sql_echo = True
        mock_create_engine.return_value = MagicMock(spec=Engine)

        session_module.get_engine()

        _, kwargs = mock_create_engine.call_args
        assert kwargs["echo"] is True


class TestGetSessionFactory:
    @patch("app.db.session.get_engine")
    def test_returns_sessionmaker_bound_to_engine(self, mock_get_engine):
        mock_engine = MagicMock(spec=Engine)
        mock_get_engine.return_value = mock_engine

        factory = session_module.get_session_factory()

        assert isinstance(factory, sessionmaker)
        # The factory should be bound to the engine
        assert factory.kw["bind"] is mock_engine

    @patch("app.db.session.get_engine")
    def test_factory_creates_sessions(self, mock_get_engine):
        mock_engine = MagicMock(spec=Engine)
        mock_get_engine.return_value = mock_engine

        factory = session_module.get_session_factory()
        sess = factory()

        assert sess is not None
        sess.close()


class TestGetSession:
    @patch("app.db.session.get_session_factory")
    def test_yields_session_and_closes(self, mock_factory_fn):
        mock_session = MagicMock()
        mock_factory = MagicMock(return_value=mock_session)
        mock_factory_fn.return_value = mock_factory

        gen = session_module.get_session()
        sess = next(gen)

        assert sess is mock_session

        # Exhaust the generator (trigger finally block)
        with pytest.raises(StopIteration):
            next(gen)

        mock_session.close.assert_called_once()

    @patch("app.db.session.get_session_factory")
    def test_closes_session_on_exception(self, mock_factory_fn):
        mock_session = MagicMock()
        mock_factory = MagicMock(return_value=mock_session)
        mock_factory_fn.return_value = mock_factory

        gen = session_module.get_session()
        sess = next(gen)
        assert sess is mock_session

        # Simulate an exception in the consumer
        with contextlib.suppress(ValueError):
            gen.throw(ValueError("test error"))

        mock_session.close.assert_called_once()
