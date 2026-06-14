"""Typer CLI for the FundSmart triage service."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

# The repo contains a root folder named "typer". When the repo root is on
# sys.path, that folder can shadow the installed Typer package. Remove the root
# before importing Typer so this module works as a project console script.
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) in sys.path:
    sys.path.remove(str(ROOT))
if "" in sys.path:
    sys.path.remove("")

import requests
import typer
from dotenv import load_dotenv
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

load_dotenv(ROOT / ".env", override=False)
load_dotenv(ROOT / "services/triage_service/.env", override=False)

console = Console()

app = typer.Typer(
    name="triage",
    help="CLI for sending complaint text files to the FundSmart triage service.",
    add_completion=True,
    no_args_is_help=True,
)

HEADER_PATTERN = re.compile(
    r"^\*\*(?P<label>Channel|Received|Customer ID|Subject|Thread context|Agent|Duration|Note):\*\*\s*(?P<value>.*)$",
    re.IGNORECASE,
)
HEADER_FIELD_MAP = {
    "channel": "channel",
    "received": "received",
    "customer id": "customer_id",
    "subject": "subject",
    "thread context": "thread_context",
    "agent": "agent",
    "duration": "duration",
    "note": "note",
}


def service_url_from_env() -> str:
    return (
        os.getenv("TRIAGE_SERVICE_URL")
        or os.getenv("TRIAGE_API_URL")
        or "http://localhost:8001"
    ).rstrip("/")


def api_key_from_env() -> str | None:
    return os.getenv("TRIAGE_SERVICE_API_KEY")


def request_headers(api_key: str | None) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def read_input(file_path: Path | None, text: str | None) -> str:
    if text is not None:
        return text
    if file_path is not None:
        return file_path.read_text(encoding="utf-8")
    if not sys.stdin.isatty():
        return sys.stdin.read()
    raise typer.BadParameter(
        "Provide a text file, --text, or pipe complaint text through stdin."
    )


def parse_markdown_metadata(document: str) -> dict[str, str]:
    metadata: dict[str, str] = {}
    for line in document.splitlines():
        match = HEADER_PATTERN.match(line.strip())
        if not match:
            continue
        label = match.group("label").strip().lower()
        field = HEADER_FIELD_MAP.get(label)
        value = match.group("value").strip()
        if field and value:
            metadata[field] = value
    return metadata


def looks_like_complaint_document(text: str) -> bool:
    return "**Channel:**" in text or "**Received:**" in text or "```" in text


def build_metadata(
    document: str,
    channel: str | None,
    received: str | None,
    customer_id: str | None,
    subject: str | None,
    thread_context: str | None,
    agent: str | None,
    duration: str | None,
    note: str | None,
) -> dict[str, str | None]:
    metadata: dict[str, str | None] = {
        "channel": channel,
        "received": received,
        "customer_id": customer_id,
        "subject": subject,
        "thread_context": thread_context,
        "agent": agent,
        "duration": duration,
        "note": note,
    }
    parsed = parse_markdown_metadata(document)
    for key, value in parsed.items():
        metadata[key] = metadata.get(key) or value
    return metadata


def build_complaint_document(
    text: str,
    metadata: dict[str, str | None],
    as_is: bool,
) -> str:
    stripped = text.strip()
    if as_is or looks_like_complaint_document(stripped):
        return stripped

    labels = [
        ("Channel", metadata.get("channel")),
        ("Received", metadata.get("received")),
        ("Customer ID", metadata.get("customer_id")),
        ("Subject", metadata.get("subject")),
        ("Thread context", metadata.get("thread_context")),
        ("Agent", metadata.get("agent")),
        ("Duration", metadata.get("duration")),
        ("Note", metadata.get("note")),
    ]
    header_lines = [f"**{label}:** {value}" for label, value in labels if value]
    if not header_lines:
        return stripped
    return "\n".join(header_lines) + f"\n\n```\n{stripped}\n```"


def print_list_table(title: str, values: list[str]) -> None:
    if not values:
        return
    table = Table(title=title, box=box.SIMPLE_HEAVY, show_lines=False)
    table.add_column("#", justify="right", style="dim", no_wrap=True)
    table.add_column("Value")
    for index, value in enumerate(values, start=1):
        table.add_row(str(index), str(value))
    console.print(table)


def print_result(body: dict[str, Any]) -> None:
    triage = body.get("triage") or {}
    metadata = body.get("metadata") or {}
    extracted_metadata = triage.get("extracted_metadata") or {}

    summary = Table(title="FundSmart triage result", box=box.SIMPLE_HEAVY)
    summary.add_column("Field", style="bold", no_wrap=True)
    summary.add_column("Value")
    summary.add_row("id", str(body.get("id") or ""))
    summary.add_row("run_id", str(body.get("run_id") or "not persisted"))
    summary.add_row("version", str(metadata.get("version") or ""))
    summary.add_row("latency_seconds", f"{float(body.get('latency_seconds') or 0):.3f}")
    summary.add_row("category", str(triage.get("category") or ""))
    summary.add_row("severity", str(triage.get("severity") or ""))
    summary.add_row("routing", str(triage.get("recommended_routing") or ""))
    summary.add_row("sla", str(triage.get("sla_recommendation") or ""))
    summary.add_row("acknowledgement_valid", str(metadata.get("acknowledgement_valid")))
    summary.add_row("critical_risk", str(metadata.get("critical_risk")))
    console.print(summary)

    if extracted_metadata:
        meta_table = Table(title="Extracted metadata", box=box.SIMPLE_HEAVY)
        meta_table.add_column("Field", style="bold", no_wrap=True)
        meta_table.add_column("Value")
        for key, value in extracted_metadata.items():
            if value is not None:
                meta_table.add_row(str(key), str(value))
        console.print(meta_table)

    complaint_summary = triage.get("complaint_summary")
    reasoning = triage.get("reasoning")
    acknowledgement = body.get("acknowledgement_draft")
    if complaint_summary:
        console.print(
            Panel(str(complaint_summary), title="Complaint summary", border_style="blue")
        )
    if reasoning:
        console.print(Panel(str(reasoning), title="Reasoning", border_style="cyan"))
    if acknowledgement:
        console.print(
            Panel(str(acknowledgement), title="Acknowledgement draft", border_style="green")
        )

    print_list_table("Detected signals", triage.get("detected_signals") or [])
    print_list_table("Vulnerability signals", triage.get("vulnerability_signals") or [])
    print_list_table("Regulatory flags", triage.get("regulatory_flags") or [])
    print_list_table("Customer preferences", triage.get("customer_preferences") or [])

    validation_errors = metadata.get("acknowledgement_validation_errors") or []
    print_list_table("Acknowledgement validation errors", validation_errors)


@app.command()
def health(
    service_url: str = typer.Option(
        service_url_from_env(),
        "--service-url",
        help="Base URL for the triage service.",
    ),
    api_key: Optional[str] = typer.Option(  # noqa: UP007,UP045
        None,
        "--api-key",
        help="Bearer token. Defaults to TRIAGE_SERVICE_API_KEY.",
    ),
    timeout: float = typer.Option(30.0, "--timeout", help="Request timeout in seconds."),
) -> None:
    """Check the triage service health endpoint."""
    resolved_api_key = api_key or api_key_from_env()
    try:
        response = requests.get(
            f"{service_url.rstrip('/')}/health",
            headers=request_headers(resolved_api_key),
            timeout=timeout,
        )
        response.raise_for_status()
    except requests.HTTPError as exc:
        detail = exc.response.text if exc.response is not None else str(exc)
        console.print(
            f"[red][bold]error:[/bold] HTTP failure from triage service[/red]\n{detail}"
        )
        raise typer.Exit(1) from exc
    except requests.RequestException as exc:
        console.print(f"[red][bold]error:[/bold] request failed[/red] {exc}")
        raise typer.Exit(1) from exc
    console.print_json(data=response.json())


@app.command()
def send(
    file_path: Optional[Path] = typer.Argument(  # noqa: UP007,UP045
        None,
        exists=True,
        dir_okay=False,
        readable=True,
        help="Path to a .txt/.md complaint document. Omit to read stdin.",
    ),
    text: Optional[str] = typer.Option(  # noqa: UP007,UP045
        None,
        "--text",
        help="Complaint text supplied directly on the command line.",
    ),
    complaint_id: Optional[str] = typer.Option(  # noqa: UP007,UP045
        None,
        "--id",
        help="Complaint id. Defaults to cli-<random>.",
    ),
    version: str = typer.Option("v2", "--version", help="Pipeline version: v1 or v2."),
    service_url: str = typer.Option(
        service_url_from_env(),
        "--service-url",
        help="Base URL for the triage service.",
    ),
    api_key: Optional[str] = typer.Option(  # noqa: UP007,UP045
        None,
        "--api-key",
        help="Bearer token. Defaults to TRIAGE_SERVICE_API_KEY.",
    ),
    timeout: float = typer.Option(300.0, "--timeout", help="Request timeout in seconds."),
    source: str = typer.Option("cli", "--source", help="Source value sent to the service."),
    as_is: bool = typer.Option(
        False,
        "--as-is",
        help="Send text exactly as complaint_document without metadata wrapping.",
    ),
    raw_json: bool = typer.Option(
        False,
        "--json",
        help="Print the raw service response JSON.",
    ),
    channel: Optional[str] = typer.Option(None, "--channel", help="Complaint channel."),  # noqa: UP007,UP045
    received: Optional[str] = typer.Option(None, "--received", help="Received timestamp."),  # noqa: UP007,UP045
    customer_id: Optional[str] = typer.Option(None, "--customer-id", help="Customer ID."),  # noqa: UP007,UP045
    subject: Optional[str] = typer.Option(None, "--subject", help="Complaint subject."),  # noqa: UP007,UP045
    thread_context: Optional[str] = typer.Option(None, "--thread-context", help="Thread context."),  # noqa: UP007,UP045
    agent: Optional[str] = typer.Option(None, "--agent", help="Agent name for call transcript input."),  # noqa: UP007,UP045
    duration: Optional[str] = typer.Option(None, "--duration", help="Call duration."),  # noqa: UP007,UP045
    note: Optional[str] = typer.Option(None, "--note", help="Additional source note."),  # noqa: UP007,UP045
) -> None:
    """Send a complaint text file to `/triage` and print the result."""
    input_text = read_input(file_path, text)
    metadata = build_metadata(
        document=input_text,
        channel=channel,
        received=received,
        customer_id=customer_id,
        subject=subject,
        thread_context=thread_context,
        agent=agent,
        duration=duration,
        note=note,
    )
    complaint_document = build_complaint_document(input_text, metadata, as_is=as_is)
    payload = {
        "id": complaint_id or f"cli-{uuid4().hex[:10]}",
        "source": source,
        "complaint_document": complaint_document,
        "metadata": metadata,
    }
    resolved_api_key = api_key or api_key_from_env()
    try:
        response = requests.post(
            f"{service_url.rstrip('/')}/triage",
            params={"version": version},
            headers=request_headers(resolved_api_key),
            json=payload,
            timeout=timeout,
        )
        response.raise_for_status()
    except requests.HTTPError as exc:
        detail = exc.response.text if exc.response is not None else str(exc)
        console.print(
            f"[red][bold]error:[/bold] HTTP failure from triage service[/red]\n{detail}"
        )
        raise typer.Exit(1) from exc
    except requests.RequestException as exc:
        console.print(f"[red][bold]error:[/bold] request failed[/red] {exc}")
        raise typer.Exit(1) from exc

    body = response.json()
    if raw_json:
        console.print_json(data=body)
        return
    print_result(body)


if __name__ == "__main__":
    app()
