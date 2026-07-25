"""Cloudflare Python Workers entrypoint."""

from hayate.adapters.workers import to_workers

from translation_hub.app import app

Default = to_workers(app)
